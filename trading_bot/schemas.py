# schemas.py
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TradingViewSignal(BaseModel):
    secret: str
    symbol: str
    side: Literal["buy", "sell"]
    qty: Annotated[float, Field(ge=0.01, lt=1.0)]
    price: Annotated[float, Field(ge=1.0)]
    trigger_time: datetime
    max_lag: int
    strategy_id: str

    model_config = {"extra": "forbid"}
