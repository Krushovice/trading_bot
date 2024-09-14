import os
import time
import traceback

from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

from .api import Bybit
import logging

logger = logging.getLogger(__name__)


class Bot(Bybit):
    def __init__(self, max_usdt_to_spend=10, interval=1):
        super(Bot, self).__init__()
        self.max_usdt_to_spend = int(max_usdt_to_spend)
        self.spent_usdt = 0  # Инициализация потраченных средств
        self.interval = interval
        self.price_decimals, self.qty_decimals, self.min_qty = (
            self.get_instrument_info()
        )

        logger.info(
            "Bot initialized with max USDT to spend: %s", self.max_usdt_to_spend
        )

    def can_place_order(self, order_cost):
        """Проверяет, можно ли разместить ордер, не превышая лимит на расходы."""
        can_place = (self.spent_usdt + order_cost) <= self.max_usdt_to_spend
        logger.debug(
            f"Checking if order can be placed: {can_place} (order cost: {order_cost}, spent USDT: {self.spent_usdt})"
        )
        return can_place

    def calculate_indicators(self, data):
        """Рассчитывает индикаторы для входных данных."""
        try:
            data["RSI"] = RSIIndicator(data["close"], window=13).rsi()
            bollinger = BollingerBands(data["close"], window=19, window_dev=2)
            data["Bollinger_High"] = bollinger.bollinger_hband()
            data["Bollinger_Low"] = bollinger.bollinger_lband()
            data["Bollinger_Mid"] = bollinger.bollinger_mavg()
            logger.info("Indicators calculated successfully.")
        except Exception as e:
            logger.error(f"Failed to calculate indicators: {e}")
            logger.error(traceback.format_exc())
        return data

    def generate_signal(self, data):
        """
        Генерирует торговый сигнал на основе данных.
        :param data: DataFrame с историческими данными
        :return: Торговый сигнал (1 - Buy, 0 - Sell, None - No Signal)
        """
        try:
            data = self.calculate_indicators(data)
            print("Входящие данные:")

            latest_data = data.iloc[-1]
            print(latest_data)
            buy_condition = (latest_data["close"] < latest_data["Bollinger_Low"]) and (
                latest_data["RSI"] <= 35
            )
            sell_condition = (
                latest_data["close"] > latest_data["Bollinger_High"]
            ) and (latest_data["RSI"] >= 65)

            logger.debug(
                f"Latest close price: {latest_data['close']}, "
                f"Bollinger Low: {latest_data['Bollinger_Low']},"
                f" Bollinger High: {latest_data['Bollinger_High']}, "
                f"RSI: {latest_data['RSI']}"
            )

            if buy_condition:
                logger.info("Buy condition met.")
                return 1  # Buy signal
            elif sell_condition:
                logger.info("Sell condition met.")
                return 0  # Sell signal
            else:
                logger.info("No trading signal generated.")
        except Exception as e:
            logger.error(f"Exception occurred during signal generation: {e}")
            logger.error(traceback.format_exc())
        return None

    def adjust_qty(self, qty):
        """Корректирует количество ордера в зависимости от минимально допустимого размера."""
        min_order_value_in_base = self._floor(
            self.min_qty / (10**self.price_decimals), self.qty_decimals
        )

        if qty < min_order_value_in_base:
            qty = min_order_value_in_base

        return qty

    def get_valid_order_qty(self, current_symbol_price):
        min_notional = 20  # Минимальная сумма в USDT
        qty = self.floor_qty(min_notional / current_symbol_price)
        return qty

    def _floor(self, value, decimals):
        """
        Для аргументов цены нужно отбросить (округлить вниз)
        до колва знаков заданных в фильтрах цены
        """
        factor = 1 / (10**decimals)
        return (value // factor) * factor

    def floor_qty(self, value):
        return self._floor(value, self.qty_decimals)

    def execute_trade_by_base(
        self,
        signal,
    ):
        side = "Buy" if signal == 1 else "Sell"
        curr_price = self.get_symbol_price(self.symbol)
        valid_qty = self.get_valid_order_qty(
            current_symbol_price=curr_price,
        )

        try:
            self.set_trailing_stop(
                trailing_percent=0.0002,
            )
        except Exception as e:
            logger.error(f"Failed to set trailing stop: {e}")
        try:
            order = self.place_order(side=side, qty=valid_qty)
            logger.info(f"Executed {side} order for base {self.symbol}: {order}")
            return order
        except Exception as e:
            logger.error(f"Exception occurred while executing trade: {e}")
            logger.error(traceback.format_exc())

    def run(self):
        """Основной цикл работы бота."""

        while True:
            try:

                logger.info("The Bot is starting!")
                self.check_permissions()
                logger.info("Permissions checked successfully.")
                latest_data = self.get_historical_data()

                if latest_data is None:
                    logger.error(f"Failed to fetch latest data for {self.symbol}.")
                    time.sleep(self.interval)
                    continue

                signal = self.generate_signal(latest_data)

                if signal is not None:
                    print(signal)
                    try:

                        if self.execute_trade_by_base(signal):
                            print("Ордер успешно размещен")

                    except Exception as e:
                        logger.error(f"Exception occurred while executing trade: {e}")

                else:
                    logger.info("No signal generated.")
                    print("Нет сигнала")

            except Exception as e:
                logger.error(f"Exception occurred in main loop: {e}")
                logger.error(traceback.format_exc())

            time.sleep(self.interval)  # Sleep for 1 second
