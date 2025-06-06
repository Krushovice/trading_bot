from datetime import datetime, timezone
import os
import traceback

from fastapi import (
    BackgroundTasks,
    HTTPException,
    Request,
    Response,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from trade_service.schemas import TradingViewSignal
from trade_service.trade_logic import TradeService
from utils import normalize_symbol, setup_logger
from webhook_service.app_utils import alert_telegram_admins

from .setup_app import setup_app


SECRET_KEY = os.getenv("MY_SECRET_KEY")
ALERT_PATH = os.getenv("ALERT_PATH")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
TRADE_PATH = os.getenv("TRADE_PATH")
BOT_PREFIX = os.getenv("BOT_PREFIX")

MAX_MSG_LENGTH = 4095


logger = setup_logger(__name__)

# Передаём SlowAPIMiddleware через класс Middleware
middleware = [Middleware(SlowAPIMiddleware)]

app = setup_app(middleware=middleware)

# Rate-limiter: до 10 вызовов / минуту
limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter  # type: ignore[attr-defined]

# Инициализируем сервис с торговой логикой
trade_service = TradeService()


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Полный traceback
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    lines = tb.splitlines()
    short_tb = "\n".join(lines[:15])  # первые 15 строк
    if len(short_tb) < MAX_MSG_LENGTH:
        # Краткое сообщение для телеги
        error_message = (
            f"🚨 <b>UNHANDLED ERROR</b>\n"
            f"🔗 <b>URL:</b> {request.url}\n\n"
            f"<pre>{short_tb}</pre>"
        )
    else:
        short_tb = short_tb[:10]
        error_message = (
            f"🚨 <b>UNHANDLED ERROR</b>\n"
            f"🔗 <b>URL:</b> {request.url}\n\n"
            f"<pre>{short_tb}</pre>"
        )
    # Лог в файл
    logger.critical(
        "🔥 Unhandled exception at %s\n%s",
        request.url,
        tb,
    )

    # Телега (внутри alert_telegram_admins есть защита и лог)
    try:
        await alert_telegram_admins(error_message)
    except Exception as e:
        logger.error("⚠️ Failed to alert Telegram: %s", e)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.middleware("http")
async def only_webhook_middleware(
    request: Request,
    call_next,
):
    bot_webhook_path = f"{BOT_PREFIX}{WEBHOOK_PATH}"
    alert_path = f"{BOT_PREFIX}{ALERT_PATH}"
    allowed_paths = {TRADE_PATH, bot_webhook_path, alert_path}

    if request.url.path not in allowed_paths:
        return Response(status_code=404)
    return await call_next(request)


@app.post(TRADE_PATH)
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
    order_id = trade_service.execute_trade(
        symbol=symbol,
        side=signal.side,
        qty=signal.qty,
    )

    if order_id:
        # Фоновая задача будет ждать исполнения и ставить SL
        background_tasks.add_task(
            trade_service.wait_for_fill_and_set_sl,
            order_id=order_id,
            symbol=signal.symbol,
            side=signal.side,
        )

    return {"status": "ok"}
