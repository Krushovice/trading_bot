import pytest


def test_get_instruments_info_success(monkeypatch, bybit):
    """
    Успешный сценарий: resp["retCode"] = 0, список не пуст,
    и мы ожидаем правильный кортеж (min_qty, tick_size, qty_step, price_decimals).
    """
    # 1) Подготовим фиктивный ответ:
    fake_resp = {
        "retCode": 0,
        "result": {
            "list": [
                {
                    # Значения в ответе приходят в виде строк, преобразуем их в float/int внутри метода
                    "lotSizeFilter": {
                        "minOrderQty": "0.1",  # min_qty = 0.1
                        "qtyStep": "0.01",  # qty_step = 0.01
                    },
                    "priceFilter": {
                        "tickSize": "0.5",  # tick_size = 0.5
                    },
                    # Необязательный ключ priceScale: если не указан, метод возьмёт default=4
                    "priceScale": 3,  # price_decimals = 3
                }
            ]
        },
    }

    # 2) Подменяем метод клиентa, чтобы он возвращал fake_resp.
    #    Обратите внимание: сигнатура должна совпадать с вызовом в коде:
    #      self.client.get_instruments_info(symbol=symbol, category=self.category)
    monkeypatch.setattr(
        bybit.client,
        "get_instruments_info",
        lambda symbol, category: fake_resp,
    )

    # 3) Вызовем тестируемый метод
    out = bybit.get_instruments_info("BTCUSDT")

    # 4) Проверяем, что получен кортеж из 4 элементов
    assert isinstance(out, tuple) and len(out) == 4

    min_qty, tick_size, qty_step, price_decimals = out
    assert min_qty == 0.1  # из "0.1"
    assert tick_size == 0.5  # из "0.5"
    assert qty_step == 0.01  # из "0.01"
    assert price_decimals == 3  # из 3


@pytest.mark.parametrize(
    "resp_data",
    [
        # 1) retCode != 0 → возвращаем None
        {"retCode": 1, "result": {"list": []}, "retMsg": "error"},
        # 2) retCode = 0, но список пустой → возвращаем None
        {"retCode": 0, "result": {"list": []}, "retMsg": None},
    ],
)
def test_get_instruments_info_failure(
    resp_data,
    bybit,
    monkeypatch,
):
    """
    Варианты, когда метод должен вернуть None:
      - retCode != 0
      - пустой список (resp["result"]["list"] == [])
    """
    monkeypatch.setattr(
        bybit.client,
        "get_instruments_info",
        lambda symbol, category: resp_data,
    )
    assert bybit.get_instruments_info("ETHUSDT") is None


def test_get_instruments_info_exception(bybit, monkeypatch):
    """
    Симулируем ситуацию, когда self.client.get_instruments_info бросает исключение.
    В таком случае метод отлавливает его и возвращает None.
    """

    def raiser(symbol, category):
        raise Exception("network error")

    monkeypatch.setattr(
        bybit.client,
        "get_instruments_info",
        raiser,
    )
    assert bybit.get_instruments_info("XRPUSDT") is None
