# schemas.py
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, constr


class TradingViewSignal(BaseModel):
    secret: str
    symbol: str
    side: Annotated[str, constr(min_length=3, max_length=4)]
    qty: Annotated[float, Field(ge=0.01, lt=1.0)]
    price: float
    trigger_time: datetime
    max_lag: int
    strategy_id: str
