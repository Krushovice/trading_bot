from datetime import datetime
import random

import pytest


@pytest.fixture()
def valid_webhook_data():
    return {
        "secret": "abide1234",  # любая строка
        "symbol": "SYMBOL",  # любая строка
        "side": random.choice(["buy", "sell"]),  # строго нижний регистр
        "qty": round(random.uniform(0.01, 0.9999), 4),  # ≥ 0.01 и < 1.0
        "price": round(random.uniform(1.0, 100.0), 2),  # ≥ 1.0
        "trigger_time": datetime.now(),
        "max_lag": random.randint(0, 60),  # любое int ≥ 0
        "strategy_id": "1234hed",  # любая строка
    }


@pytest.fixture()
def unexpected_webhook_data():
    return {
        "secret": "abide1234",
        "symbol": "SYMBOL",
        "side": random.choice(["buy", "sell"]),
        "qty": round(random.uniform(0.01, 0.9999), 4),
        "price": round(random.uniform(1.0, 100.0), 2),
        "unexpected_field": 123,
        "trigger_time": datetime.now(),
        "max_lag": 1,
        "strategy_id": "1234hed",
    }


@pytest.fixture()
def invalid_values_webhook_data():
    return {
        "secret": "abide1234",
        "symbol": "SYMBOL",
        "side": random.choice(["Buy", "SELL", "bUy"]),
        "qty": random.choice((0.0, -0.5, 1.0, 5.0)),
        "price": random.choice((0.0, 0.5, -10.0)),
        "trigger_time": datetime.now(),
        "max_lag": -1,  # < 0 – тоже невалидно (ожидаем int ≥ 0)
        "strategy_id": "1234hed",
    }
