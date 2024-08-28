import logging
import os

import pandas as pd
from pybit.unified_trading import HTTP, AccountHTTP, MarketHTTP
from pybit import exceptions

logger = logging.getLogger("krushovice_trade")


class Bybit:
    """
    Класс Bybit реализует логику взаимодействия с биржей Bybit
    торговой логике в нем нет
    """

    def __init__(self):
        logger.info(f"{os.getenv('NAME', 'Anon')} Bybit auth logged")

        # для определения позиции
        self.position_id = "AzzraelCodeYT"

        # загрузка значения из переменных окружения,
        # чтобы при изменении окружения после запуска бота, бот продолжал нормально работать
        self.symbol = os.getenv("SYMBOL")
        self.qty = float(os.getenv("QTY"))

        # На данный момент SDK python-okx предоставляет отдельные классы к каждой секции
        # вместо единого клиента (хотя он в SDK есть, поэтому, надеюсь такой расклад не надолго)
        # чтобы не дублировать параметры для каждого класса - в конструкторе инициализирую словарь настроек
        self.params = dict(
            api_key=os.getenv("API_KEY", "1"),
            api_secret=os.getenv("API_SECRET", "1"),
        )
        self.client = HTTP(**self.params)

    def check_permissions(self):
        """
        Простой запрос к состоянию баланса Аккаунта
        для проверки прав доступа предоставленных ключей,
        если ключи не правильные выкинет ошибку
        """
        try:
            response = AccountHTTP.get_wallet_balance(accountType="UNIFIED")
            return response
        except exceptions.InvalidRequestError as e:
            logger.error(e)
        except exceptions.FailedRequestError as e:
            logger.error(e)

    def close_prices(self, instId, timeframe="1m", limit=100):
        """
        Возвращаю серию цен закрытия (close) Pandas для обработки в библиотеке ta
        :param timeframe:
        :param instId:
        :param limit:
        :return:
        """
        klines = (
            MarketAPI(**self.params)
            .get_candlesticks(instId, limit=limit, bar=timeframe)
            .get("data", [])
        )
        klines.reverse()
        return pd.Series([float(e[4]) for e in klines])

    def place_order(self, side):
        """
        Размещение заявки
        :param side:
        :return:
        """
        r = TradeAPI(**self.params).place_order(
            instId=self.symbol,
            tdMode="cash",
            side=side,
            ordType="market",
            sz=self.qty,
            tgtCcy="base_ccy",
            clOrdId=self.position_id,
        )

        order_id = None
        if r.get("code") == "0":
            # ордер успешно отправлен (но не обязательно исполнен)
            order_id = r.get("data", [])[0].get("ordId")
            logger.info(f"{side} {order_id}")
        else:
            logger.error(r)

        return order_id

    def is_position(self):
        """
        Ищем открытую позицию по clOrdId
        За 3 месяца макс !!!!
        :return:
        """
        orders = (
            TradeAPI(**self.params)
            .get_orders_history(
                instType="SPOT", instId=self.symbol, ordType="market", state="filled"
            )
            .get("data", [])
        )

        for o in orders:
            if o.get("clOrdId") != self.position_id:
                continue
            logger.debug(f"Order_id:{o.get('ordId')} {o.get('side')}")
            return o.get("side") == "buy"

        return False
