import os
import time
import traceback

from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

from .api import Bybit

from .logger import setup_logger
from .storage import PositionStorage

logger = setup_logger(__name__)


class Bot(Bybit):
    def __init__(
        self,
        storage,
        max_usdt_to_spend=10,
        interval=300,
    ):
        super().__init__()
        self.storage = storage
        self.max_usdt_to_spend = max_usdt_to_spend
        self.interval = interval
        self.fast_ema_period = int(os.getenv("FAST_EMA_LEN"))
        self.slow_ema_period = int(os.getenv("SLOW_EMA_LEN"))
        self.sr_period = int(os.getenv("SR_PERIOD"))
        self.buffer_pct = float(os.getenv("BUFFER_PCT"))
        self.atr_period = int(os.getenv("ATR_PERIOD"))
        self.atr_mult = float(os.getenv("ATR_MULT"))
        self.vol_sma_period = int(os.getenv("VOL_SMA_PERIOD"))

    def calculate_indicators(self, data):
        # Явное преобразование типов данных
        data["close"] = data["close"].astype(float)
        data["high"] = data["high"].astype(float)
        data["low"] = data["low"].astype(float)
        data["volume"] = data["volume"].astype(float)

        # EMA с fillna=True
        data["fast_ema"] = EMAIndicator(
            close=data["close"],
            window=self.fast_ema_period,
            fillna=True,
        ).ema_indicator()
        data["slow_ema"] = EMAIndicator(
            close=data["close"],
            window=self.slow_ema_period,
            fillna=True,
        ).ema_indicator()

        # Support и Resistance
        data["support"] = data["low"].rolling(self.sr_period).min()
        data["resistance"] = data["high"].rolling(self.sr_period).max()

        # Буферные зоны входа
        data["support_upper"] = data["support"] * (1 + self.buffer_pct / 100)
        data["resistance_lower"] = data["resistance"] * (1 - self.buffer_pct / 100)

        # ATR и средний ATR
        atr_indicator = AverageTrueRange(
            high=data["high"],
            low=data["low"],
            close=data["close"],
            window=self.atr_period,
            fillna=True,
        )
        data["atr"] = atr_indicator.average_true_range()
        data["avg_atr"] = data["atr"].rolling(self.atr_period).mean()

        # Средний объем за период
        data["vol_sma"] = data["volume"].rolling(self.vol_sma_period).mean()

        return data

    def volatility_filter(self, latest):
        volume_condition = latest["volume"] > latest["vol_sma"]
        atr_condition = latest["atr"] > latest["avg_atr"] * self.atr_mult
        return volume_condition and atr_condition

    def generate_signal(self, data):
        latest = data.iloc[-1]

        trend_up = latest["fast_ema"] > latest["slow_ema"]
        trend_down = latest["fast_ema"] < latest["slow_ema"]

        long_entry = trend_up and (
            latest["support_upper"] >= latest["low"] >= latest["support"]
        )
        short_entry = trend_down and (
            latest["resistance_lower"] <= latest["high"] <= latest["resistance"]
        )

        # Проверка фильтра волатильности и объёма
        volatility_ok = self.volatility_filter(latest)

        # Проверяем текущие открытые позиции
        positions = self.get_open_positions()
        position_side = positions[0]["side"] if positions else None

        # Сигналы входа с учётом фильтра волатильности
        if long_entry and volatility_ok:
            if position_side != "Buy":
                return "Buy"
        elif short_entry and volatility_ok:
            if position_side != "Sell":
                return "Sell"

        # Сигналы выхода по TP
        if position_side == "Buy" and latest["high"] >= latest["resistance"]:
            return "Close_Buy"
        if position_side == "Sell" and latest["low"] <= latest["support"]:
            return "Close_Sell"

        return None

    def execute_trade(self, signal, latest_data):
        positions = self.get_open_positions()
        current_side = positions[0]["side"] if positions else None
        position_qty = sum(float(p["size"]) for p in positions) if positions else 0

        qty = round(100 / latest_data["close"], self.qty_decimals)

        try:
            if signal == "Buy":
                limit_price = latest_data["support_upper"]

                if current_side == "Sell":
                    self.place_order("Buy", position_qty, limit_price)
                    logger.info(f"🔄 Переворот Short → Long по {limit_price}")

                if current_side != "Buy" or len(positions) < 2:
                    order_id = self.place_order("Buy", qty, limit_price)
                    if order_id:
                        self.set_stop_loss("Buy", limit_price)
                        logger.info(f"📈 Long лимитный ордер на {qty} по {limit_price}")

            elif signal == "Sell":
                limit_price = latest_data["resistance_lower"]

                if current_side == "Buy":
                    self.place_order("Sell", position_qty, limit_price)
                    logger.info(f"🔄 Переворот Long → Short по {limit_price}")

                if current_side != "Sell" or len(positions) < 2:
                    order_id = self.place_order("Sell", qty, limit_price)
                    if order_id:
                        self.set_stop_loss("Sell", limit_price)
                        logger.info(f"📉 Short лимитный ордер на {qty} по {limit_price}")

            elif signal == "Close_Buy" and current_side == "Buy":
                tp_price = latest_data["resistance"]
                self.place_order("Sell", position_qty, tp_price)
                self.storage.clear_position(self.symbol)
                logger.info(f"✅ Закрытие Long позиции по TP на уровне {tp_price}")

            elif signal == "Close_Sell" and current_side == "Sell":
                tp_price = latest_data["support"]
                self.place_order("Buy", position_qty, tp_price)
                self.storage.clear_position(self.symbol)
                logger.info(f"✅ Закрытие Short позиции по TP на уровне {tp_price}")

        except Exception as e:
            logger.error(f"Ошибка исполнения лимитного ордера: {e}", exc_info=True)



    def run(self):
        position = self.storage.load_position(self.symbol)
        logger.info(f"🚩 Текущее состояние позиции: {position}")

        while True:
            try:
                data = self.get_historical_data()
                if data.empty:
                    logger.warning("Нет исторических данных. Повторный запрос...")
                    time.sleep(self.interval)
                    continue

                data = self.calculate_indicators(data)
                signal = self.generate_signal(data)
                latest_data = data.iloc[-1]

                if signal:
                    logger.info(f"⚡️ Получен сигнал: {signal}")
                    self.execute_trade(signal, latest_data)
                else:
                    logger.info("🔕 Нет сигнала.")

            except Exception as e:
                logger.error(f"Ошибка в цикле работы: {e}", exc_info=True)

            time.sleep(self.interval)
