import logging
import os
import uuid

import pandas as pd
from pybit.unified_trading import HTTP, AccountHTTP, MarketHTTP, TradeHTTP
from pybit import exceptions

from Logger import setup_logger

logger = setup_logger(__name__)


class Bybit:
    """
    Класс Bybit реализует логику взаимодействия с биржей Bybit
    торговой логике в нем нет
    """

    def __init__(self):
        logger.info(f"{os.getenv('NAME', 'Anon')} Bybit auth logged")

        # # для определения позиции
        self.position_id = str(uuid.uuid4())
        #
        # # загрузка значения из переменных окружения,
        # # чтобы при изменении окружения после запуска бота, бот продолжал нормально работать
        self.symbol = os.getenv("SYMBOL")
        self.qty = str(os.getenv("QTY"))

        # На данный момент SDK python-okx предоставляет отдельные классы к каждой секции
        # вместо единого клиента (хотя он в SDK есть, поэтому, надеюсь такой расклад не надолго)
        # чтобы не дублировать параметры для каждого класса - в конструкторе инициализирую словарь настроек
        self.params = dict(
            api_key=os.getenv("API_KEY"),
            api_secret=os.getenv("API_SECRET"),
        )
        self.client = HTTP(**self.params)

    def check_permissions(self):
        """
        Простой запрос к состоянию баланса Аккаунта
        для проверки прав доступа предоставленных ключей,
        если ключи не правильные выкинет ошибку
        """
        try:
            response = AccountHTTP(**self.params).get_wallet_balance(
                accountType="UNIFIED"
            )
            return response
        except exceptions.InvalidRequestError as e:
            logger.error(e)
        except exceptions.FailedRequestError as e:
            logger.error(e)

    def close_prices(
        self,
        symbol,
        interval="1",
        limit=100,
        category="inverse",
    ):
        """
        Возвращает серию цен закрытия (close) Pandas для обработки в библиотеке ta.
        :param symbol: Символ инструмента (например, "BTCUSD")
        :param interval: Временной интервал свечей (например, 1, 3, 5, 15 минут и т.д.)
        :param limit: Количество свечей для получения
        :param category: Категория инструмента (например, "inverse" для обратных контрактов)
        :return: pd.Series с ценами закрытия
        """
        # Получаем текущие данные о свечах
        response = self.client.get_kline(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        # Проверяем, что запрос был успешным
        if response["retCode"] == 0:
            klines = response["result"]["list"]
            # Разворачиваем список свечей, чтобы он был в хронологическом порядке
            klines.reverse()
            # Извлекаем цены закрытия и возвращаем их в виде Pandas серии
            return pd.Series([float(e[4]) for e in klines])
        else:
            logger.error(response["retMsg"])
            raise Exception(f"Ошибка получения данных: {response['retMsg']}")

    def place_order(self, side):
        """
        Размещение заявки на Bybit.
        :param side: Сторона сделки ("Buy" или "Sell")
        :return: order_id если заявка успешно размещена, иначе None
        """
        try:
            response = TradeHTTP(**self.params).place_order(
                category="spot",  # Укажите категорию продукта (например, "spot", "linear", "inverse")
                symbol=self.symbol,  # Укажите символ (например, "BTCUSDT")
                side=side,  # Сторона сделки ("Buy" или "Sell")
                orderType="Market",  # Тип ордера (в данном случае "Market")
                qty=str(self.qty),  # Количество для ордера
                timeInForce="IOC",  # Указываем время выполнения, по умолчанию "IOC" для Market ордеров
                orderLinkId=self.position_id,  # Уникальный идентификатор ордера
            )

            order_id = None
            if response.get("retCode") == 0:
                # Ордер успешно отправлен
                order_id = response.get("result", {}).get("orderId")
                logger.info(f"{side} order placed with order ID: {order_id}")
            else:
                # Логирование ошибки, если запрос не успешен
                logger.error(f"Failed to place order: {response.get('retMsg')}")

            return order_id
        except Exception as e:
            # Логирование исключений
            logger.error(f"Exception occurred while placing order: {e}")
            return None

    def is_position(self):
        """
        Ищем открытую позицию по orderLinkId (clOrdId) за последние 7 дней.
        Возвращает True, если позиция была открыта с типом buy, иначе False.
        """
        # Параметры запроса
        params = {
            "category": "spot",  # Тип продукта (например, spot)
            "symbol": self.symbol,  # Торговая пара (например, BTCUSDT)
            "orderType": "Market",  # Тип ордера (например, Market)
            "orderLinkId": self.position_id,  # Пользовательский идентификатор ордера
            "orderStatus": "Filled",  # Ищем только исполненные ордера
        }

        # Выполнение запроса к API
        response = self.client.get_order_history(**params)

        # Получаем список ордеров
        orders = response.get("result", {}).get("list", [])

        # Ищем нужный ордер по orderLinkId и проверяем его сторону
        for order in orders:
            if order.get("orderLinkId") == self.position_id:
                logger.debug(f"Order_id:{order.get('orderId')} {order.get('side')}")
                return order.get("side") == "Buy"

        # Если ордер не найден, возвращаем False
        return False
