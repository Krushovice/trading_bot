import os
import ta
import traceback
import numpy as np
import pandas as pd
from time import sleep
from .api import Bybit
from .logger import setup_logger

logger = setup_logger(__name__)


class Bot(Bybit):
    """
    Класс Bot реализует логику торговли, наследуя методы взаимодействия с биржей Bybit.
    """

    def __init__(self):
        super(Bot, self).__init__()

        self.timeout = int(os.getenv("TIMEOUT", 240))
        self.interval = os.getenv("INTERVAL", "5")

        # Инициализация переменных для торговой стратегии
        self.capital = float(os.getenv("CAPITAL", 10000))
        self.position = 0
        self.entry_price = 0
        self.buy_stage = 0

    def calculate_macd(self, close):
        macd = ta.trend.MACD(close)
        macd_line = macd.macd()
        macd_signal_line = macd.macd_signal()
        macd_diff = macd_line - macd_signal_line
        return macd_line, macd_signal_line, macd_diff

    def get_indicators(self):
        close = self.close_prices(symbol=self.symbol, interval=self.interval)
        macd, macd_signal, macd_diff = self.calculate_macd(close)

        logger.debug(f"macd_diff type: {type(macd_diff)}")
        if isinstance(macd_diff, pd.Series):
            if macd_diff.empty:
                logger.error("MACD difference series is empty.")
                return None, None, None
            else:
                # Проверяем, что значения в серии - числа
                if not all(isinstance(value, (float, int)) for value in macd_diff):
                    logger.error(
                        f"Unexpected value types in macd_diff: {[type(value) for value in macd_diff]}"
                    )
                    return None, None, None
        elif isinstance(macd_diff, (float, int)):
            pass
        else:
            logger.error(f"Unexpected type for macd_diff: {type(macd_diff)}")
            return None, None, None

        return macd, macd_signal, macd_diff

    def trading_logic(self):
        try:
            # Получаем информацию о символе: количество знаков после запятой для цены и количества, минимальное количество
            instrument_info = self.get_instrument_info(self.symbol)
            if not instrument_info:
                logger.error("Failed to get instrument info.")
                return

            price_decimals, qty_decimals, min_qty = instrument_info

            # Получаем индикаторы
            macd, macd_signal, macd_diff = self.get_indicators()
            prices = self.close_prices(symbol=self.symbol, interval=self.interval)

            if prices.empty:
                logger.error("No price data available.")
                return

            current_price = prices.iloc[-1]

            # Проверка корректности значений в macd_diff
            if (
                isinstance(macd_diff, pd.Series)
                and not macd_diff.empty
                and isinstance(macd_diff.iloc[-1], (float, int))
            ):
                macd_value = macd_diff.iloc[-1]

                # Получение текущей цены символа в USDT
                current_symbol_price = self.get_symbol_price(self.symbol)
                if current_symbol_price is None:
                    logger.error(f"Could not retrieve price for {self.symbol}.")
                    return

                # Проверка на соответствие размера лота
                def is_valid_order(amount):
                    """Проверка, достаточно ли количество валюты для минимального ордера в USDT."""
                    amount_in_usdt = amount * current_symbol_price
                    return amount_in_usdt >= 5  # 5 USDT — минимальное значение ордера

                # Округление количества с учетом количества знаков после запятой
                def round_qty(qty):
                    return round(qty, qty_decimals)

                # Округление цены с учетом количества знаков после запятой
                def round_price(price):
                    return round(price, price_decimals)

                if macd_value > -25 and self.buy_stage == 0:
                    buy_amount = self.capital * 0.3
                    buy_amount = round_qty(buy_amount)
                    if buy_amount >= min_qty and is_valid_order(buy_amount):
                        self.capital -= buy_amount
                        self.position += buy_amount / current_price
                        self.entry_price = round_price(current_price)
                        self.buy_stage = 1
                        self.place_order("Buy", buy_amount)
                        logger.info(f"First buy at {self.entry_price}")

                elif macd_value > -45 and self.buy_stage == 1:
                    buy_amount = self.capital * 0.3
                    buy_amount = round_qty(buy_amount)
                    if buy_amount >= min_qty and is_valid_order(buy_amount):
                        self.capital -= buy_amount
                        self.position += buy_amount / current_price
                        self.buy_stage = 2
                        self.place_order("Buy", buy_amount)
                        logger.info(f"Second buy at {current_price}")

                elif macd_value > -65 and self.buy_stage == 2:
                    buy_amount = self.capital * 0.3
                    buy_amount = round_qty(buy_amount)
                    if buy_amount >= min_qty and is_valid_order(buy_amount):
                        self.capital -= buy_amount
                        self.position += buy_amount / current_price
                        self.buy_stage = 3
                        self.place_order("Buy", buy_amount)
                        self.set_stop_loss(self.symbol, "Buy", self.entry_price * 0.96)
                        logger.info(f"Third buy at {current_price}")

                if macd_value > 30 and self.buy_stage == 3:
                    logger.info(f"MACD above 30, enabling trailing stop loss")
                    self.enable_trailing_stop_loss(
                        self.symbol, "Buy", current_price * 0.04
                    )

            else:
                logger.error(f"Unexpected value in macd_diff: {macd_diff}")

        except Exception as e:
            logger.error(f"Exception occurred in trading logic: {e}")

    def check(self):
        """
        Проверка сигналов и выполнение торговой логики.
        """
        try:
            self.trading_logic()
        except Exception as e:
            logger.error(f"Error in check: {e}")
            logger.error(traceback.format_exc())

    def loop(self):
        """
        Цикл проверки.
        """
        while True:
            self.check()
            sleep(self.timeout)

    def run(self):
        """
        Инициализация бота.
        """
        try:
            logger.info("The Bot is starting!")
            self.check_permissions()
            logger.info("Permissions checked successfully.")
            self.loop()
        except Exception as e:
            logger.error(f"Error in run method: {e}")
            logger.error(traceback.format_exc())
