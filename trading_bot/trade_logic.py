import os

from .bybit import Bybit

from utils.logger import setup_logger

logger = setup_logger(__name__)


class Bot(Bybit):
    def __init__(self, storage):
        super().__init__()
        self.max_entries = int(os.getenv("MAX_ENTRIES", 1))
        self.storage = storage

    def verify_position_with_exchange(self, symbol):
        positions = self.get_open_positions(symbol)
        if positions:
            total_qty = sum(float(p["size"]) for p in positions)
            side = positions[0]["side"]
            entries = len(positions)
            self.storage.save_position(
                symbol, {"side": side, "total_qty": total_qty, "entries": entries}
            )
            logger.info("✅ Позиция синхронизирована с биржей")
        else:
            self.storage.clear_position(symbol)
            logger.info("⚠️ Нет открытых позиций на бирже, Redis очищен.")

    def execute_trade(
        self,
        symbol,
        side,
        qty,
        limit_price,
    ):
        instrument_info = self.get_instruments_info(symbol)
        if instrument_info:
            price_decimals, qty_decimals, min_qty = instrument_info
        else:
            logger.error(f"Не удалось получить данные инструмента {symbol}")
            return

        position = self.storage.load_position(symbol)
        current_side = position.get("side")
        entries = position.get("entries", 0)
        total_qty = position.get("total_qty", 0)

        if entries >= self.max_entries:
            logger.warning(
                f"🔔 Лимит ордеров ({self.max_entries}) для {symbol} уже достигнут."
            )
            return

        qty = round(qty, qty_decimals)

        try:
            if side == "Buy":
                if current_side == "Sell":
                    close_order_id = self.place_order(
                        symbol,
                        "Buy",
                        total_qty,
                        limit_price,
                    )
                    if close_order_id:
                        self.storage.clear_position(symbol)
                        entries, total_qty = 0, 0
                        logger.info(
                            f"🔄 Переворот Short → Long ({symbol}) по цене {limit_price}"
                        )

                order_id = self.place_order(
                    symbol,
                    "Buy",
                    qty,
                    limit_price,
                )
                if order_id:
                    self.set_stop_loss(
                        symbol,
                        "Buy",
                        limit_price,
                        price_decimals,
                    )
                    self.storage.save_position(
                        symbol,
                        {
                            "side": "Buy",
                            "total_qty": total_qty + qty,
                            "entries": entries + 1,
                        },
                    )
                    logger.info(
                        f"📈 Long лимитный ордер {symbol}: {qty} по цене {limit_price}"
                    )

            elif side == "Sell":
                if current_side == "Buy":
                    close_order_id = self.place_order(
                        symbol,
                        "Sell",
                        total_qty,
                        limit_price,
                    )
                    if close_order_id:
                        self.storage.clear_position(symbol)
                        entries, total_qty = 0, 0
                        logger.info(
                            f"🔄 Переворот Long → Short ({symbol}) по цене {limit_price}"
                        )

                order_id = self.place_order(
                    symbol,
                    "Sell",
                    qty,
                    limit_price,
                )
                if order_id:
                    self.set_stop_loss(
                        symbol,
                        "Sell",
                        limit_price,
                        price_decimals,
                    )
                    self.storage.save_position(
                        symbol,
                        {
                            "side": "Sell",
                            "total_qty": total_qty + qty,
                            "entries": entries + 1,
                        },
                    )
                    logger.info(
                        f"📉 Short лимитный ордер {symbol}: {qty} по цене {limit_price}"
                    )

        except Exception as e:
            logger.error(
                f"Ошибка исполнения ордера для {symbol}: {e}",
                exc_info=True,
            )
