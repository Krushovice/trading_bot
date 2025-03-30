# schemas.py
from pydantic import BaseModel
from datetime import datetime


class TradingViewSignal(BaseModel):
    symbol: str
    side: str
    qty: float
    price: float
    trigger_time: datetime
    max_lag: int
    strategy_id: str
