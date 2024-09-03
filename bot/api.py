import decimal
import os
import uuid

import inspect

import pandas as pd
from pybit.unified_trading import HTTP, AccountHTTP, MarketHTTP, TradeHTTP
from pybit import exceptions

from . import setup_logger

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
        interval="5",
        limit=200,
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
        args = dict(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        try:
            self.log("args", args)
            # Получаем текущие данные о свечах
            response = MarketHTTP(**self.params).get_kline(**args)

            # Проверяем, что запрос был успешным
            if response["retCode"] == 0:
                klines = response["result"]["list"]

                if not klines:
                    logger.error(f"No kline data returned for {symbol}.")
                    return pd.Series()

                # Разворачиваем список свечей, чтобы он был в хронологическом порядке
                klines.reverse()

                # Извлекаем цены закрытия и возвращаем их в виде Pandas серии
                try:
                    close_prices = [float(e[4]) for e in klines]
                    return pd.Series(close_prices)
                except (IndexError, ValueError) as e:
                    logger.error(f"Error processing kline data: {e}")
                    return pd.Series()

            else:
                logger.error(f"API response error: {response['retMsg']}")
                raise Exception(f"Ошибка получения данных: {response['retMsg']}")
        except Exception as e:
            logger.error(f"Exception occurred in close_prices: {e}")
            return pd.Series()

    def get_instrument_info(self, symbol):
        try:
            response = MarketHTTP(**self.params).get_instruments_info(
                category="linear",
                symbol=symbol,
            )
            if response.get("retCode") == 0:
                c = response.get("result", {}).get("list", [])
                min_qty = c.get("lotSizeFilter", {}).get("minOrderQty", "0.0")
                qty_decimals = abs(decimal.Decimal(min_qty).as_tuple().exponent)
                price_decimals = int(c.get("priceScale", "4"))
                min_qty = float(min_qty)
                self.log(price_decimals, qty_decimals, min_qty)
                return price_decimals, qty_decimals, min_qty
            logger.error("Failed to retrieve instrument information.")
            return None
        except Exception as e:
            logger.error(
                f"Exception occurred while retrieving instrument information: {e}"
            )
            return None

    def get_symbol_price(self, symbol):
        """
        Получает текущую цену указанного символа.
        :param symbol: Символ для поиска (например, "DOGEUSDT")
        :return: Текущая цена символа в float или None в случае ошибки
        """
        try:
            response = MarketHTTP(**self.params).get_tickers(
                category="linear",
                symbol=symbol,
            )
            if response.get("retCode") == 0:
                symbols = response["result"]["list"]
                for item in symbols:
                    self.log(float(item["ask1Price"]))
                    return float(item["ask1Price"])
            else:
                logger.error(
                    f"Failed to retrieve coin information: {response.get('retMsg')}"
                )
                return None
        except Exception as e:
            logger.error(f"Exception occurred while retrieving coin information: {e}")
            return None

    def place_order(self, side, qty):
        """
        Размещение заявки на Bybit.
        :param side: Сторона сделки ("Buy" или "Sell")
        :param qty: Количество контрактов
        :return: order_id если заявка успешно размещена, иначе None
        """
        args = dict(
            category="linear",
            symbol=self.symbol,
            side=side,
            orderType="Market",
            qty=str(qty),
            timeInForce="IOC",
            orderLinkId=self.position_id,
        )

        try:
            self.log("args", args)
            response = TradeHTTP(**self.params).place_order(**args)

            order_id = None
            if response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId")
                logger.info(f"{side} order placed with order ID: {order_id}")
            else:
                logger.error(f"Failed to place order: {response.get('retMsg')}")

            return order_id
        except Exception as e:
            logger.error(f"Exception occurred while placing order: {e}")
            return None

    def set_stop_loss(self, symbol, side, stop_loss_price):
        """
        Устанавливает стоп-лосс для открытой позиции.
        :param symbol: Символ инструмента (например, "BTCUSDT")
        :param side: Сторона сделки ("Buy" или "Sell")
        :param stop_loss_price: Цена, на которой будет установлен стоп-лосс
        """
        args = dict(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            orderType="StopLoss",
            qty=str(self.qty),
            stopLossPrice=stop_loss_price,
            timeInForce="IOC",
        )
        try:
            self.log("args", args)
            response = TradeHTTP(**self.params).place_order(**args)

            if response.get("retCode") == 0:
                logger.info(f"Stop loss set at {stop_loss_price} for {side} order")
            else:
                logger.error(f"Failed to set stop loss: {response.get('retMsg')}")

        except Exception as e:
            logger.error(f"Exception occurred while setting stop loss: {e}")

    def enable_trailing_stop_loss(self, symbol, side, trailing_offset):
        """
        Устанавливает трейлинг стоп-лосс для открытой позиции.
        :param symbol: Символ инструмента (например, "BTCUSDT")
        :param side: Сторона сделки ("Buy" или "Sell")
        :param trailing_offset: Отклонение для трейлинг стопа
        """
        args = dict(
            category="linear",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            orderType="TrailingStop",
            qty=str(self.qty),
            trailingOffset=trailing_offset,
            timeInForce="IOC",
        )
        try:
            self.log("args", args)
            response = TradeHTTP(**self.params).place_order(**args)

            if response.get("retCode") == 0:
                logger.info(
                    f"Trailing stop loss set with offset {trailing_offset} for {side} order"
                )
            else:
                logger.error(
                    f"Failed to set trailing stop loss: {response.get('retMsg')}"
                )

        except Exception as e:
            logger.error(f"Exception occurred while setting trailing stop loss: {e}")

    def get_historical_data(self, symbol, interval="5", limit=200):
        """
        Получает исторические данные для символа из API биржи.

        :param symbol: Символ для получения данных (например, "BTCUSD").
        :param interval: Интервал времени для данных (например, '5' для 5 минут).
        :param limit: Количество данных для получения.
        :return: DataFrame с историческими данными.
        """
        try:
            close_prices = self.close_prices(symbol, interval, limit)
            if close_prices.empty:
                logger.error(f"No historical data returned for {symbol}.")
                return None

            df = pd.DataFrame({"close": close_prices})
            return df

        except Exception as e:
            logger.error(f"Exception occurred while fetching historical data: {e}")
            return None

    def get_latest_data(self, symbol, interval="5"):
        """
        Получает самые свежие данные для символа из API биржи.

        :param symbol: Символ для получения данных (например, "BTCUSD").
        :param interval: Интервал времени для данных (например, '5' для 5 минут).
        :return: DataFrame с последними данными.
        """
        try:
            close_prices = self.close_prices(symbol, interval, limit=1)
            if close_prices.empty:
                logger.error(f"No latest data returned for {symbol}.")
                return None

            df = pd.DataFrame({"close": close_prices})
            return df

        except Exception as e:
            logger.error(f"Exception occurred while fetching latest data: {e}")
            return None

    def is_position(self):
        """
        Ищем открытую позицию по orderLinkId (clOrdId) за последние 7 дней.
        Возвращает True, если позиция была открыта с типом buy, иначе False.
        """
        # Параметры запроса
        params = {
            "category": "linear",  # Тип продукта (например, spot)
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

    def log(self, *args):
        """
        Для удобного вывода из методов класса
        """
        caller = inspect.stack()[1].function
        print(f"* {caller}", self.symbol, "\n\t", args, "\n")
