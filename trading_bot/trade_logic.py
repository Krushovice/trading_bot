import os

from .bybit import Bybit

from utils.logger import setup_logger

logger = setup_logger(__name__)


class Bot(Bybit):
    def __init__(
        self,
        storage,
    ):
        super().__init__()
        self.storage = storage
        self.max_entries = os.getenv("MAX_ENTRIES", 1)

    def verify_position_with_exchange(self):
        positions = self.get_open_positions()
        if positions:
            total_qty = sum(float(p["size"]) for p in positions)
            side = positions[0]["side"]
            entries = len(positions)
            self.storage.save_position(
                self.symbol, {"side": side, "total_qty": total_qty, "entries": entries}
            )
            logger.info("✅ Позиция синхронизирована с биржей")
        else:
            self.storage.clear_position(self.symbol)
            logger.info("⚠️ Нет открытых позиций на бирже, Redis очищен.")

    def execute_trade(self, side, qty, limit_price):
        position = self.storage.load_position(self.symbol)
        current_side = position.get("side")
        entries = position.get("entries", 0)
        total_qty = position.get("total_qty", 0)

        try:
            if side == "Buy":
                if current_side == "Sell":
                    self.place_order("Buy", total_qty, limit_price)
                    self.storage.clear_position(self.symbol)
                    entries, total_qty = 0, 0
                    logger.info("🔄 Short → Long переворот")

                if entries < self.max_entries:
                    order_id = self.place_order("Buy", qty, limit_price)
                    if order_id:
                        self.set_stop_loss("Buy", limit_price)
                        self.storage.save_position(
                            self.symbol,
                            {
                                "side": "Buy",
                                "total_qty": total_qty + qty,
                                "entries": entries + 1,
                            },
                        )
                        logger.info("📈 Long ордер размещён")

            elif side == "Sell":
                if current_side == "Buy":
                    self.place_order("Sell", total_qty, limit_price)
                    self.storage.clear_position(self.symbol)
                    entries, total_qty = 0, 0
                    logger.info("🔄 Long → Short переворот")

                if entries < self.max_entries:
                    order_id = self.place_order("Sell", qty, limit_price)
                    if order_id:
                        self.set_stop_loss("Sell", limit_price)
                        self.storage.save_position(
                            self.symbol,
                            {
                                "side": "Sell",
                                "total_qty": total_qty + qty,
                                "entries": entries + 1,
                            },
                        )
                        logger.info("📉 Short ордер размещён")
        except Exception as e:
            logger.error(f"Ошибка торговли: {e}", exc_info=True)
