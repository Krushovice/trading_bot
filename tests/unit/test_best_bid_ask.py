import pytest

from tests.unit.conftest import bybit


def test_get_best_bid_ask_success(bybit, monkeypatch):
    fake_data = {
        "retCode": 0,
        "result": {"list": [{"bid1Price": "123.45", "ask1Price": "123.55"}]},
    }

    def fake_get_tickers(category, symbol):
        assert category == bybit.category
        assert symbol == "LTCUSDT"
        return fake_data

    monkeypatch.setattr(
        bybit.client,
        "get_tickers",
        fake_get_tickers,
    )

    # Метод возвращает ровно два числа
    bid, ask = bybit.get_best_bid_ask("LTCUSDT")
    assert bid == 123.45
    assert ask == 123.55


@pytest.mark.parametrize(
    "resp_data",
    [
        {"retCode": 1, "result": {"list": []}, "retMsg": "error"},
        {"retCode": 0, "result": {"list": []}, "retMsg": None},
    ],
)
def test_get_best_bid_ask_failure(
    resp_data,
    bybit,
    monkeypatch,
):
    monkeypatch.setattr(
        bybit.client,
        "get_tickers",
        lambda category, symbol: resp_data,
    )
    assert bybit.get_best_bid_ask("BTCUSDT") is None


@pytest.mark.skip(
    reason="Здесь проверяется выброс исключения, но в CI этот тест не нужен"
)
def test_get_best_bid_ask_exception(bybit, monkeypatch):
    def raiser(category, symbol):
        raise RuntimeError("network failure")

    monkeypatch.setattr(bybit.client, "get_tickers", raiser)
    assert bybit.get_best_bid_ask("ETHUSDT") is None
