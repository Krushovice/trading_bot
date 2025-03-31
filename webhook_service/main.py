from fastapi import FastAPI, BackgroundTasks
from trading_bot.schemas import TradingViewSignal
from trading_bot.trade_logic import Bot

from datetime import datetime, timezone

from utils.logger import setup_logger
from utils.storage import PositionStorage


logger = setup_logger(__name__)

app = FastAPI()

storage = PositionStorage()

bot = Bot()


@app.post("/trading_webhook")
async def handle_webhook(
    signal: TradingViewSignal,
    background_tasks: BackgroundTasks,
):
    logger.info(f"🔔 Webhook получен: {signal}")
    background_tasks.add_task(process_signal, signal)
    return {"status": "received"}


def process_signal(signal: TradingViewSignal):

    now = datetime.now(timezone.utc)
    lag = (now - signal.trigger_time).total_seconds()
    if lag > signal.max_lag:
        logger.warning(f"Сигнал слишком старый (задержка {lag}s > {signal.max_lag}s).")
        return

    bot.execute_trade(
        signal.symbol,
        signal.side,
        signal.qty,
        signal.price,
    )
    # После исполнения сделки обновляем позиции:
    # bot.verify_position_with_exchange(signal.symbol)
