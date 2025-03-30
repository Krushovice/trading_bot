from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from trading_bot.trade_logic import Bot
from utils.logger import setup_logger
from utils.storage import PositionStorage

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(_):
    bot.verify_position_with_exchange()
    yield


app = FastAPI(lifespan=lifespan)
storage = PositionStorage()
bot = Bot(storage=storage)


@app.post("/trading_webhook")
async def webhook(request: Request):
    data = await request.json()
    side = data["side"]
    symbol = data["symbol"]
    limit_price = float(data["limit_price"])
    qty = float(data["qty"])

    logger.info(f"Webhook: {side} {symbol} qty: {qty} at price: {limit_price}")
    res = bot.execute_trade(side, qty, limit_price)

    return {"status": "ok"}
