import os

from fastapi import HTTPException

from trading_bot.schemas import TradingViewSignal


SECRET_KEY = os.getenv("MY_SECRET_KEY")


async def validate_secret(signal: TradingViewSignal) -> None:

    if signal.secret != SECRET_KEY:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid secret",
        )
