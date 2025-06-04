import pytest

from trading_bot import Bybit


class DummyClient:
    def get_instruments_info(self, symbol, category):
        # Если не будет замены через monkeypatch, тест упадёт
        # мы хотим гарантированно подменять этот метод
        raise RuntimeError("unmocked!")

    def get_tickers(self, category, symbol):
        raise RuntimeError("unmocked!")


@pytest.fixture
def bybit(monkeypatch):
    b = Bybit(use_testnet=True)

    b.client = DummyClient()
    return b
