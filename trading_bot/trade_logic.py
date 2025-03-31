import os

from .bybit import Bybit

from utils.logger import setup_logger

logger = setup_logger(__name__)


class Bot(Bybit):
    def __init__(self):
        super().__init__()
        # Разрешаем всего 2 сделки (1 основная + 1 догрузка)
        self.max_entries = int(os.getenv("MAX_ENTRIES", "1"))
        self.entries = 0  # счётчик открытий (не хранится после перезапуска)
        self.current_side = None  # текущее направление (Buy / Sell)
        self.current_qty = 0.0  # текущий объём

    def execute_trade(self, symbol: str, side: str, qty: float, limit_price: float):
        instrument_info = self.get_instruments_info(symbol)
        if not instrument_info:
            logger.error(f"Не удалось получить инструменты для {symbol}")
            return

        price_decimals, qty_decimals, min_qty = instrument_info
        signal_qty = round(qty, qty_decimals)
        limit_price = round(limit_price, price_decimals)

        logger.info(
            f"🚀 Сигнал: {symbol}, side={side}, qty={signal_qty}, price={limit_price}"
        )

        # Сначала проверим, есть ли позиция на бирже (может у нас Market не исполнен?)
        positions = self.get_open_positions(symbol)
        if positions:
            # У Bybit USDT-маржинального обычно одна позиция (size > 0)
            bybit_side = positions[0]["side"]  # 'Buy' or 'Sell'
            bybit_qty = float(positions[0]["size"])
            logger.info(
                f"🗄 Биржа: есть позиция side={bybit_side}, qty={bybit_qty} {symbol}"
            )
        else:
            bybit_side = None
            bybit_qty = 0.0
            logger.info(f"🗄 Биржа: нет открытых позиций по {symbol}")

        # Если у нас в памяти current_side не совпадает с bybit_side,
        # обновим локально (доверяем бирже, раз уж не храним в Redis)
        if bybit_side != self.current_side:
            self.current_side = bybit_side
            self.current_qty = bybit_qty
            self.entries = 1 if bybit_side else 0

        logger.info(
            f"🔍 Локальная память: side={self.current_side}, entries={self.entries}, qty={self.current_qty}"
        )

        # Если сигнал приходит на Buy, но есть позиция Sell -> переворот
        if side == "Buy" and self.current_side == "Sell" and self.current_qty > 0:
            close_order_id = self.place_order(
                symbol, "Buy", self.current_qty, limit_price
            )
            if close_order_id:
                logger.info(
                    f"🔄 Переворот Short → Long. Закрыли {self.current_qty} {symbol}"
                )
                self.current_side = None
                self.current_qty = 0
                self.entries = 0
            else:
                logger.error("❌ Не удалось перевернуть позицию")
                return

        # Если сигнал приходит на Sell, а позиция Buy
        if side == "Sell" and self.current_side == "Buy" and self.current_qty > 0:
            close_order_id = self.place_order(
                symbol, "Sell", self.current_qty, limit_price
            )
            if close_order_id:
                logger.info(
                    f"🔄 Переворот Long → Short. Закрыли {self.current_qty} {symbol}"
                )
                self.current_side = None
                self.current_qty = 0
                self.entries = 0
            else:
                logger.error("❌ Не удалось перевернуть позицию")
                return

        # Если entries >= max_entries и текущая сторона совпадает с сигналом -> отказываем
        if self.current_side == side and self.entries >= self.max_entries:
            logger.warning(
                f"🔔 Достигнут лимит ордеров {self.max_entries} для {symbol}."
            )
            return

        # Размещаем лимитный ордер на вход
        order_id = self.place_order(symbol, side, signal_qty, limit_price)
        if order_id:
            self.set_stop_loss(symbol, side, limit_price, price_decimals)
            logger.info(f"✅ Открыли {side} {signal_qty} {symbol} по {limit_price}")

            # Обновляем локальные переменные
            if self.current_side is None:
                self.current_side = side
                self.current_qty = signal_qty
                self.entries = 1
            elif self.current_side == side:
                self.current_qty += signal_qty
                self.entries += 1
            else:
                # Если не совпало - логика переворота
                self.current_side = side
                self.current_qty = signal_qty
                self.entries = 1
        else:
            logger.error("⚠️ Не удалось разместить ордер на вход")
