from datetime import datetime, timezone
import os

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from trading_bot.schemas import TradingViewSignal
from trading_bot.trade_logic import Bot
from utils import normalize_symbol, setup_logger


load_dotenv()
SECRET_KEY = os.getenv("MY_SECRET_KEY")
logger = setup_logger(__name__)

# Rate-limiter: до 10 вызовов / минуту
limiter = Limiter(key_func=get_remote_address)

# Передаём SlowAPIMiddleware через класс Middleware
middleware = [Middleware(SlowAPIMiddleware)]
app = FastAPI(
    middleware=middleware,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.state.limiter = limiter  # ignore


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    logger.error(
        "❌ Validation failed: %s → %s",
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too Many Requests"},
    )


@app.middleware("http")
async def only_webhook_middleware(
    request: Request,
    call_next,
):
    if request.url.path != "/trading_webhook":
        return Response(status_code=404)
    return await call_next(request)


bot = Bot()


@app.post("/trading_webhook")
@limiter.limit("10/minute")
async def handle_webhook(
    request: Request,
    signal: TradingViewSignal,
    background_tasks: BackgroundTasks,
):
    # Проверка секрета из TradingView
    if signal.secret != SECRET_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid secret",
        )

    logger.info(
        "🔔 Webhook от TradingView: symbol=%s, side=%s, qty=%s, price=%s",
        signal.symbol,
        signal.side,
        signal.qty,
        signal.price,
    )

    # Проверяем, чтобы сигнал был не старее max_lag (секунды)
    now = datetime.now(timezone.utc)
    lag = (now - signal.trigger_time).total_seconds()
    if lag > signal.max_lag:
        logger.warning(
            "Сигнал слишком старый: lag=%.1f > max_lag=%s",
            lag,
            signal.max_lag,
        )
        return {"status": "ignored_old"}

    # Важно: signal.symbol нужно нормализовать (например, "BTCUSD" → "BTCUSDT")
    symbol = normalize_symbol(signal.symbol)

    # Выполняем ордер: получим order_id или None
    order_id = bot.execute_trade(
        symbol=symbol,
        side=signal.side,
        qty=signal.qty,
    )

    if order_id:
        # Фоновая задача будет ждать исполнения и ставить SL
        background_tasks.add_task(
            bot.wait_for_fill_and_set_sl,
            order_id=order_id,
            symbol=signal.symbol,
            side=signal.side,
        )

    return {"status": "ok"}
