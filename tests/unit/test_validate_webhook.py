from datetime import datetime
import random

from pydantic import ValidationError
import pytest

from trade_service.schemas import TradingViewSignal


@pytest.mark.parametrize(
    "payload, expect_exception",
    [
        pytest.param(
            {
                "secret": "abide1234",
                "symbol": "SYMBOL",
                "side": random.choice(["buy", "sell"]),  # lower‐case
                "qty": round(random.uniform(0.01, 0.9999), 4),
                "price": round(random.uniform(1.0, 100.0), 2),
                "trigger_time": datetime.now(),
                "max_lag": 10,
                "strategy_id": "1234hed",
            },
            None,
            id="valid_payload",
        ),
        pytest.param(
            {
                "secret": "abide1234",
                "symbol": "SYMBOL",
                "side": random.choice(["buy", "sell"]),
                "qty": round(random.uniform(0.01, 0.9999), 4),
                "price": round(random.uniform(1.0, 100.0), 2),
                "trigger_time": datetime.now(),
                "max_lag": 10,
                "strategy_id": "1234hed",
                "unexpected": 123,
            },
            ValidationError,
            id="extra_field_forbid",
        ),
        pytest.param(
            {
                "secret": "abide1234",
                "symbol": "SYMBOL",
                "side": random.choice(["Buy", "SELL", "bUy"]),  # не lower
                "qty": 0.5,
                "price": 10.0,
                "trigger_time": datetime.now(),
                "max_lag": 10,
                "strategy_id": "1234hed",
            },
            ValidationError,
            id="side_wrong_case",
        ),
        pytest.param(
            {
                "secret": "abide1234",
                "symbol": "SYMBOL",
                "side": "buy",
                "qty": random.choice((0.0, -0.5, 1.0, 5.0)),
                "price": 10.0,
                "trigger_time": datetime.now(),
                "max_lag": 10,
                "strategy_id": "1234hed",
            },
            ValidationError,
            id="qty_out_of_range",
        ),
        pytest.param(
            {
                "secret": "abide1234",
                "symbol": "SYMBOL",
                "side": "sell",
                "qty": 0.5,
                "price": random.choice((0.0, 0.5, -10.0)),
                "trigger_time": datetime.now(),
                "max_lag": 10,
                "strategy_id": "1234hed",
            },
            ValidationError,
            id="price_too_low",
        ),
        pytest.param(
            {
                "secret": "abide1234",
                "symbol": "SYMBOL",
                "side": "buy",
                "qty": 0.5,
                "price": 10.0,
                "trigger_time": datetime.now(),
                "strategy_id": "1234hed",
            },
            ValidationError,
            id="missing_max_lag",
        ),
    ],
)
def test_trading_view_signal_validation(payload, expect_exception):
    if expect_exception is None:
        obj = TradingViewSignal.model_validate(payload)
        assert isinstance(obj, TradingViewSignal)
    else:
        with pytest.raises(expect_exception):
            TradingViewSignal.model_validate(payload)
