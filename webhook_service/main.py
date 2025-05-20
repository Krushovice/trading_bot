from datetime import datetime, timezone

from typing import Optional

from fastapi import (
    FastAPI,
    BackgroundTasks,
    Request,
    Response,
    Depends,
)


from fastapi.middleware import Middleware


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


from trading_bot.schemas import TradingViewSignal
from trading_bot.trade_logic import Bot


from utils import (
    setup_logger,
    PositionStorage,
    normalize_symbol,
)

from .app_utils import validate_secret

logger = setup_logger(__name__)

middleware = [
    Middleware(SlowAPIMiddleware),  # type: ignore[attr-defined]
]
app = FastAPI(
    middleware=middleware,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


storage = PositionStorage()

bot = Bot()


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter  # type: ignore[attr-defined]

app.add_exception_handler(
    exc_class_or_status_code=RateLimitExceeded,
    handler=_rate_limit_exceeded_handler,  # type: ignore[attr-defined]
)


@app.middleware("http")
async def only_webhook_middleware(
    request: Request,
    call_next,
):
    if request.url.path != "/trading_webhook":
        return Response(status_code=404)
    return await call_next(request)


@app.post(
    "/trading_webhook",
    dependencies=[
        Depends(validate_secret),
        Depends(limiter.limit("10/minute")),  # по IP
        Depends(
            limiter.limit(
                "30/minute",
                key_func=lambda req: "global",
            )
        ),  # глобально
    ],
)
async def handle_webhook(
    signal: TradingViewSignal,
    background_tasks: BackgroundTasks,
):
    logger.info(
        f"🔔 Webhook: {signal.symbol=} {signal.side=}",
        f"{signal.qty=} {signal.price=}",
    )

    # Сначала исполним торговую логику:
    order_id = process_signal(signal)

    # Если order_id не None и side = 'Limit',
    if order_id:
        # добавляем фоновую задачу, чтобы дождаться исполнения и поставить SL
        background_tasks.add_task(
            bot.wait_for_fill_and_set_sl,
            order_id,
            signal,
        )

    return {"status": "ok"}


def process_signal(signal: TradingViewSignal) -> Optional[str]:
    now = datetime.now(timezone.utc)
    lag = (now - signal.trigger_time).total_seconds()
    if lag > 30:
        logger.warning(f"Сигнал слишком старый (задержка {lag}s > {signal.max_lag}s).")
        return None

    # конвертируем название символа в валидное для апи
    symbol = normalize_symbol(signal.symbol)

    # execute_trade возвращает order_id лимитного ордера (или None)
    order_id = bot.execute_trade(
        symbol,
        signal.side,
        signal.qty,
        signal.price,
    )
    if order_id:
        return order_id
    return None
