import os
import time
import traceback

from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

from .ml_model import TradingModel
from .api import Bybit
import logging

logger = logging.getLogger(__name__)


class Bot(Bybit):
    def __init__(self):
        super(Bot, self).__init__()
        self.model = TradingModel()  # Инициализация TradingModel
        self.model.load_model()  # Загружаем модель при создании объекта Bot
        self.training_interval = 3600  # Интервал для переобучения модели (1 час)
        self.last_training_time = time.time()

    def calculate_indicators(self, data):
        data["SMA_5"] = SMAIndicator(data["close"], window=5).sma_indicator()
        data["SMA_20"] = SMAIndicator(data["close"], window=20).sma_indicator()
        data["RSI"] = RSIIndicator(data["close"], window=14).rsi()
        bollinger = BollingerBands(data["close"], window=20, window_dev=2)
        data["Bollinger_High"] = bollinger.bollinger_hband()
        data["Bollinger_Low"] = bollinger.bollinger_lband()
        data["Bollinger_Mid"] = bollinger.bollinger_mavg()
        return data

    def generate_signal(self, data):
        data = self.calculate_indicators(data)
        features = data[
            [
                "SMA_5",
                "SMA_20",
                "RSI",
                "Bollinger_High",
                "Bollinger_Low",
                "Bollinger_Mid",
            ]
        ]
        features.dropna(inplace=True)

        if not features.empty:
            X = features.values  # Преобразуем DataFrame в numpy массив
            prediction = self.model.predict(
                X
            )  # Используем метод predict из TradingModel
            return prediction[-1]  # Return the last prediction
        return None

    def adjust_qty(self, qty):
        """Корректирует количество ордера в зависимости от минимально допустимого размера."""
        instrument_info = self.get_instrument_info(self.symbol)
        if not instrument_info:
            logger.error("Failed to get instrument info.")
            return qty

        price_decimals, qty_decimals, min_qty = instrument_info

        # Устанавливаем минимальное количество, если qty меньше минимального
        if qty < min_qty:
            qty = min_qty
            logger.info(f"Quantity adjusted to minimum valid amount: {qty}")

        return round(
            qty, qty_decimals
        )  # Округляем количество до допустимого количества знаков

    def execute_trade(self, signal, qty):
        symbol_price = self.get_symbol_price(self.symbol)
        if symbol_price is None:
            logger.error(f"Could not retrieve price for {self.symbol}.")
            return

        qty = self.adjust_qty(qty)  # Корректируем количество

        if not self.is_valid_order(qty, symbol_price):
            logger.error(f"Invalid quantity {qty} for trading.")
            return

        side = "Buy" if signal == 1 else "Sell"

        try:
            order = self.place_order(side=side, qty=qty)
            logger.info(f"Executed {side} order for {qty} {self.symbol}: {order}")
        except Exception as e:
            logger.error(f"Exception occurred while executing trade: {e}")

    def is_valid_order(self, qty, current_symbol_price):
        """Проверка, достаточно ли количество валюты для минимального ордера в USDT."""
        amount_in_usdt = qty * current_symbol_price
        return amount_in_usdt >= 5  # Например, минимальная сумма в USDT

    def update_model(self, new_data):
        """Переобучение модели на новых данных."""
        try:
            self.model.train(new_data)  # Переобучение модели
            self.model.save_model()  # Сохранение обновленной модели
            logger.info("Model retrained and saved.")
        except Exception as e:
            logger.error(f"Exception occurred during model update: {e}")
            logger.error(traceback.format_exc())

    def run(self):
        while True:
            try:
                latest_data = self.get_latest_data(self.symbol)
                if latest_data is None:
                    logger.error(f"Failed to fetch latest data for {self.symbol}.")
                    time.sleep(300)
                    continue

                try:
                    signal = self.generate_signal(latest_data)
                    if signal is not None:
                        qty = float(
                            os.getenv("QTY", 0.01)
                        )  # Default quantity if not set
                        self.execute_trade(signal, qty)
                except Exception as e:
                    logger.error(f"Exception occurred during trade execution: {e}")
                    logger.error(traceback.format_exc())

                # Периодическое переобучение модели
                current_time = time.time()
                if current_time - self.last_training_time >= self.training_interval:
                    try:
                        historical_data = self.get_historical_data(self.symbol)
                        if historical_data is not None:
                            self.update_model(historical_data)
                            self.last_training_time = current_time
                    except Exception as e:
                        logger.error(f"Exception occurred during model update: {e}")
                        logger.error(traceback.format_exc())

            except Exception as e:
                logger.error(f"Exception occurred in main loop: {e}")
                logger.error(traceback.format_exc())

            time.sleep(300)  # Sleep for 5 minutes
