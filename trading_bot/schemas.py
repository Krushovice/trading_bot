# schemas.py
from datetime import datetime

from pydantic import BaseModel


class TradingViewSignal(BaseModel):
    secret: str
    symbol: str
    side: str
    qty: float
    price: float
    trigger_time: datetime
    max_lag: int
    strategy_id: str
