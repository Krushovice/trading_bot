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
        redis_position = self.storage.load_position(symbol)

        if positions:
            total_qty = sum(float(p["size"]) for p in positions)
            side = positions[0]["side"]
            entries = len(positions)

            # Обновляем Redis, только если есть расхождения
            if (
                redis_position.get("total_qty") != total_qty
                or redis_position.get("side") != side
            ):
                self.storage.save_position(
                    symbol, {"side": side, "total_qty": total_qty, "entries": entries}
                )
                logger.info("✅ Позиция синхронизирована с биржей.")
            else:
                logger.info("✅ Позиция уже синхронизирована. Нет изменений.")

        else:
            # Очищаем Redis только если там были данные
            if redis_position:
                self.storage.clear_position(symbol)
                logger.info("⚠️ Нет открытых позиций на бирже, Redis очищен.")
            else:
                logger.info("ℹ️ Нет открытых позиций на бирже и в Redis.")

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

        logger.info(
            f"🔍 Проверка позиции: "
            f"current_side={current_side}, "
            f"entries={entries}, "
            f"max_entries={self.max_entries}"
        )

        if entries >= self.max_entries:
            logger.warning(
                f"🔔 Лимит ордеров ({self.max_entries}) для {symbol} уже достигнут."
            )
            return

        signal_qty = round(qty, qty_decimals)

        try:
            if side == "Buy":
                if current_side == "Sell" and total_qty > 0:
                    close_order_id = self.place_order(
                        symbol,
                        "Buy",
                        total_qty,  # Используем qty из Redis только для закрытия!
                        limit_price,
                    )
                    if close_order_id:
                        self.storage.clear_position(symbol)
                        entries, total_qty = 0, 0
                        logger.info(
                            f"🔄 Переворот Short → Long ({symbol}) по цене {limit_price}"
                        )

                # Новый лимитный ордер по сигналу
                order_id = self.place_order(
                    symbol,
                    "Buy",
                    signal_qty,  # Используем только данные сигнала TradingView
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
                            "total_qty": total_qty + signal_qty,
                            "entries": entries + 1,
                        },
                    )
                    logger.info(
                        f"📈 Long лимитный ордер {symbol}: {signal_qty} по цене {limit_price}"
                    )

            elif side == "Sell":
                if current_side == "Buy" and total_qty > 0:
                    close_order_id = self.place_order(
                        symbol,
                        "Sell",
                        total_qty,  # Используем qty из Redis только для закрытия!
                        limit_price,
                    )
                    if close_order_id:
                        self.storage.clear_position(symbol)
                        entries, total_qty = 0, 0
                        logger.info(
                            f"🔄 Переворот Long → Short ({symbol}) по цене {limit_price}"
                        )

                # Новый лимитный ордер по сигналу
                order_id = self.place_order(
                    symbol,
                    "Sell",
                    signal_qty,  # Используем только данные сигнала TradingView
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
                            "total_qty": total_qty + signal_qty,
                            "entries": entries + 1,
                        },
                    )
                    logger.info(
                        f"📉 Short лимитный ордер {symbol}: {signal_qty} по цене {limit_price}"
                    )

        except Exception as e:
            logger.error(f"Ошибка исполнения ордера для {symbol}: {e}", exc_info=True)
