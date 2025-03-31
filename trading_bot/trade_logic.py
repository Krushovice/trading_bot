import os

from .bybit import Bybit

from utils.logger import setup_logger

logger = setup_logger(__name__)


class Bot(Bybit):
    def __init__(self):
        super().__init__()
        # Логика: максимум сколько раз можно войти (например, 2)
        self.max_entries = int(os.getenv("MAX_ENTRIES", "1"))

    def execute_trade(self, symbol, side, qty, limit_price):
        """
        Сигнал от TradingView: пытаемся открыть (или перевернуть) позицию.
        - Смотрим, есть ли уже открытая позиция на Bybit
        - Если side не совпадает, сначала закрываем
        - Если не превышен max_entries, открываем новую позицию
        """

        # Сначала получаем точность цены/объёма
        instrument_info = self.get_instruments_info(symbol)
        if not instrument_info:
            logger.error(f"Не удалось получить instrument info для {symbol}")
            return

        price_decimals, qty_decimals, min_qty = instrument_info

        # Округляем входящие данные
        signal_qty = round(qty, qty_decimals)
        limit_price = round(limit_price, price_decimals)

        logger.info(
            f"🚀 Сигнал: "
            f"{symbol} side={side}, "
            f"qty={signal_qty}, "
            f"price={limit_price}"
        )

        # Смотрим, есть ли открытая позиция у Bybit
        positions = self.get_open_positions(symbol)
        current_side = None
        current_qty = 0.0

        if positions:
            # Предполагаем, что у Bybit одна активная позиция по символу + направлению
            current_side = positions[0]["side"]  # "Buy" or "Sell"
            current_qty = sum(float(p["size"]) for p in positions)

        # Для упрощения считаем, что если есть позиция, entries=1, иначе=0
        entries = 1 if current_side else 0
        logger.info(
            f"🔍 Текущая позиция на бирже: side={current_side}, qty={current_qty}, entries={entries}"
        )

        if entries >= self.max_entries and current_side == side:
            logger.warning(
                f"🔔 Достигнут лимит ордеров ({self.max_entries}) для {symbol}."
            )
            return

        # Если приходит сигнал "Buy", а уже есть позиция "Sell" → переворот
        if side == "Buy" and current_side == "Sell":
            close_order_id = self.place_order(
                symbol,
                "Buy",
                current_qty,
                limit_price,
            )
            if close_order_id:
                logger.info(
                    f"🔄 Переворот Short → Long ({symbol}). Закрыли позицию qty={current_qty}"
                )
            else:
                logger.error(f"❌ Не удалось закрыть позицию {symbol}")
                return  # Прерываем, так как переворот не состоялся

            current_side = None
            current_qty = 0.0
            entries = 0

        # Аналогично, если приходит сигнал "Sell", а уже есть позиция "Buy"
        if side == "Sell" and current_side == "Buy":
            close_order_id = self.place_order(symbol, "Sell", current_qty, limit_price)
            if close_order_id:
                logger.info(
                    f"🔄 Переворот Long → Short ({symbol}). Закрыли позицию qty={current_qty}"
                )
            else:
                logger.error(f"❌ Не удалось закрыть позицию {symbol}")
                return

            current_side = None
            current_qty = 0.0
            entries = 0

        # Теперь, если всё ок, открываем новую позицию (лимитный ордер)
        order_id = self.place_order(symbol, side, signal_qty, limit_price)
        if order_id:
            # Ставим стоп-лосс
            self.set_stop_loss(symbol, side, limit_price, price_decimals)
            logger.info(
                f"📈 Открыт ордер {symbol} {side} qty={signal_qty} по цене={limit_price}"
            )
        else:
            logger.warning(f"⚠️ Не удалось открыть новую позицию {symbol} {side}.")
