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

        self.position_id = str(uuid.uuid4())
        self.qty = os.getenv("QTY")
        self.symbol = os.getenv("SYMBOL")
        self.category = "linear"
        self.trailing_percent = os.getenv("TRAILING_PERCENT")

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
        interval="5",
        limit=200,
        category="inverse",
    ):
        """
        Возвращает серию цен закрытия (close) Pandas для обработки в библиотеке ta.
        :param interval: Временной интервал свечей (например, 1, 3, 5, 15 минут и т.д.)
        :param limit: Количество свечей для получения
        :param category: Категория инструмента (например, "inverse" для обратных контрактов)
        :return: pd.Series с ценами закрытия
        """
        args = dict(
            category=category,
            symbol=self.symbol,
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
                    logger.error(f"No kline data returned for {self.symbol}.")
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

    def get_instrument_info(self):
        """
        Фильтры заданного инструмента
        - макс колво знаков в аргументах цены,
        - мин размер ордера в Базовой Валюте,
        - макс размер ордера в БВ
        """
        r = HTTP(**self.params).get_instruments_info(
            symbol=self.symbol,
            category=self.category,
        )
        c = r.get("result", {}).get("list", [])[0]
        min_qty = c.get("lotSizeFilter", {}).get("minOrderQty", "0.0")
        qty_decimals = abs(decimal.Decimal(min_qty).as_tuple().exponent)
        price_decimals = int(c.get("priceScale", "4"))
        min_qty = float(min_qty)

        self.log(price_decimals, qty_decimals, min_qty)
        return price_decimals, qty_decimals, min_qty

    def get_symbol_price(self):
        """
        Получает текущую цену указанного символа.
        :param symbol: Символ для поиска (например, "DOGEUSDT")
        :return: Текущая цена символа в float или None в случае ошибки
        """
        try:
            response = MarketHTTP(**self.params).get_tickers(
                category=self.category,
                symbol=self.symbol,
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
            category=self.category,
            symbol=self.symbol,
            side=side,
            orderType="Market",
            qty=str(qty),
            timeInForce="IOC",
            orderLinkId=str(uuid.uuid4()),
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

    def get_open_positions(self):
        """
        Получает все активные позиции для указанного символа.
        :param symbol: Символ инструмента (например, "BTCUSD").
        :return: Список активных позиций.
        """
        try:
            response = self.client.get_positions(
                category=self.category,
                symbol=self.symbol,
            )
            if response.get("retCode") == 0:
                positions = response["result"]["list"]
                return positions
            else:
                logger.error(
                    f"Failed to retrieve open positions: {response.get('retMsg')}"
                )
                return []
        except Exception as e:
            logger.error(f"Exception occurred while retrieving open positions: {e}")
            return []

    def set_trailing_stop(self) -> None:
        """
        Устанавливает трейлинг стоп.
        """
        args = dict(
            category=self.category,
            symbol=self.symbol,
            trailingStop=str(self.trailing_percent),
            tpslMode="Full",
            positionIdx=0,
        )
        try:
            self.log("args", args)
            if self.get_open_positions()[0]["trailingStop"] == "0":
                response = HTTP(**self.params).set_trading_stop(**args)

                if response.get("retCode") == 0:
                    print("Trailing_stop was set successfully!")
                else:
                    logger.error(
                        f"Failed to set trailing stop: {response.get('retMsg')}"
                    )

        except Exception as e:
            logger.error(f"Exception occurred while setting trailing stop: {e}")

    def get_trailing_stop_limit_price(self, trades):
        """
        Получает стоп-цену.
        :param trades: Список активных трейдов
        """
        try:
            if not trades:
                logger.error("No trades to get data")
                return
            # Получение текущих цен
            df = self.get_historical_data()
            if df is None or df.empty:
                logger.error(f"No latest data returned for {self.symbol}.")
                return None

            current_price = df.iloc[0]["close"]
            new_stop_price = 0
            for trade in trades:
                if trade["type"] == "long":
                    # Обновление трейлинг-стопа для длинной позиции
                    new_stop_price = max(
                        trade["stop_price"], current_price * (1 - 0.001)
                    )
                elif trade["type"] == "short":
                    # Обновление трейлинг-стопа для короткой позиции
                    new_stop_price = min(
                        trade["stop_price"], current_price * (1 + 0.001)
                    )
                else:
                    print(trade["type"])
                if new_stop_price != trade["stop_price"]:
                    # Установка нового трейлинг-стопа

                    trade["stop_price"] = new_stop_price
                    print(new_stop_price)
                    return new_stop_price

        except Exception as e:
            logger.error(f"Exception occurred while get stop_price: {e}")

    def get_historical_data(self):
        """
        Получает исторические данные для символа из API биржи.
        :return: DataFrame с историческими данными.
        """
        try:
            close_prices = self.close_prices()
            if close_prices.empty:
                logger.error(f"No historical data returned for {self.symbol}.")
                return None

            df = pd.DataFrame({"close": close_prices})
            return df

        except Exception as e:
            logger.error(f"Exception occurred while fetching historical data: {e}")
            return None

    def is_position(self):
        """
        Ищем открытую позицию по orderLinkId (clOrdId) за последние 7 дней.
        Возвращает True, если позиция была открыта с типом buy, иначе False.
        """
        # Параметры запроса
        params = {
            "category": self.category,  # Тип продукта (например, spot)
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
        logger.debug(f"* {caller} {self.symbol} - {args}")
