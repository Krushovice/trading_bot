import os

from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from trading_bot.schemas import TradingViewSignal
from trading_bot.trade_logic import Bot

from datetime import datetime, timezone

from utils.logger import setup_logger
from utils.storage import PositionStorage
from utils.normalize import normalize_symbol

logger = setup_logger(__name__)

app = FastAPI()

storage = PositionStorage()

bot = Bot()

SECRET_KEY = os.getenv("MY_SECRET_KEY")

@app.post("/trading_webhook")
async def handle_webhook(
    signal: TradingViewSignal,
    background_tasks: BackgroundTasks,
):
    logger.info(f"🔔 Webhook получен: {signal}")

    if signal.secret != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid secret")
    # Сначала исполним торговую логику:
    order_id = process_signal(signal)

    # Если order_id не None и side = 'Limit',
    # добавляем фоновую задачу, чтобы дождаться исполнения и поставить SL
    if order_id:
        # Допустим, нам нужны symbol и side, limit_price,
        # их тоже вернём из process_signal
        background_tasks.add_task(
            bot.wait_for_fill_and_set_sl,
            order_id,
            signal,
        )

    return {"status": "ok"}


def process_signal(signal: TradingViewSignal) -> Optional[str]:
    now = datetime.now(timezone.utc)
    lag = (now - signal.trigger_time).total_seconds()
    if lag > signal.max_lag:
        logger.warning(f"Сигнал слишком старый (задержка {lag}s > {signal.max_lag}s).")
        return None
    # конвертируем название символа в валидное для апи
    symbol = normalize_symbol(signal.symbol)
    # execute_trade возвращает order_id лимитного ордера (или None)
    # получаем актуальную цену
    price = bot.get_last_price(symbol=symbol) - 0.1
    if price:
        order_id = bot.execute_trade(
            symbol,
            signal.side,
            signal.qty,
            price,
        )
        return order_id
