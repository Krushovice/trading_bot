import os
import time

from typing import Optional
from dotenv import load_dotenv

from .bybit import Bybit
from utils import setup_logger, align_to_step
from .schemas import TradingViewSignal


logger = setup_logger(__name__)

load_dotenv()


class Bot(Bybit):
    def __init__(self):
        super().__init__()
        # Разрешаем всего 2 сделки (1 основная + 1 догрузка)
        self.max_entries = int(os.getenv("MAX_ENTRIES", "1"))
        self.entries = 0  # счётчик открытий (не хранится после перезапуска)
        self.current_side = None  # текущее направление (Buy / Sell)
        self.current_qty = 0.0  # текущий объём

    def prepare_instruments(self, symbol: str) -> dict | None:
        info = self.get_instruments_info(symbol)
        if not info:
            return None
        price_dec, qty_dec, min_qty = info
        # добираем шаги
        inst_raw = self.client.get_instruments_info(symbol=symbol, category="linear")
        filters = inst_raw["result"]["list"][0]
        tick_size = float(filters["priceFilter"]["tickSize"])
        qty_step = float(filters["lotSizeFilter"]["qtyStep"])
        return {
            "price_decimals": price_dec,
            "qty_decimals": qty_dec,
            "min_qty": min_qty,
            "tick_size": tick_size,
            "qty_step": qty_step,
        }

    def prepare_trade_params(
        self,
        symbol: str,
        side: str,  # ← направление!
        qty: float,
        limit_price: float,
    ) -> tuple[float, float] | tuple[None, None]:
        inst = self.prepare_instruments(symbol)
        if not inst:
            return None, None

        # qty → кратно qty_step и ≥ min_qty
        qty = align_to_step(qty, inst["qty_step"])
        if qty < inst["min_qty"]:
            qty = inst["min_qty"]

        # price → кратно tick_size
        round_down = side.lower() == "buy"  # Buy → вниз, Sell → вверх
        price = align_to_step(
            limit_price,
            inst["tick_size"],
            round_down=round_down,
        )

        return qty, price

    def sync_position_with_bybit(self, symbol: str) -> None:
        """
        Узнаём текущую позицию на бирже и обновляем локальные переменные:
        self.current_side, self.current_qty, self.entries.
        """
        positions = self.get_open_positions(symbol)
        if positions:
            bybit_side = positions[0]["side"]  # 'Buy' / 'Sell'
            bybit_qty = float(positions[0]["size"])
            logger.info(
                f"🗄 Биржа: "
                f"есть позиция side={bybit_side}, "
                f"qty={bybit_qty} {symbol}"
            )
        else:
            bybit_side = None
            bybit_qty = 0.0
            logger.info(f"🗄 Биржа: нет открытых позиций по {symbol}")

        # Синхронизируем локальные переменные
        if bybit_side != self.current_side:
            self.current_side = bybit_side
            self.current_qty = bybit_qty
            self.entries = 1 if bybit_side else 0

        logger.info(
            f"🔍 Локальная память: "
            f"side={self.current_side}, "
            f"entries={self.entries}, "
            f"qty={self.current_qty}"
        )

    def handle_reversal_if_needed(
        self,
        symbol: str,
        signal_side: str,
        limit_price: float,
    ) -> bool:
        """
        Если у нас текущая позиция "Sell", а сигнал "Buy" (и qty>0),
        делаем переворот (закрываем Sell), обнуляем локальное состояние.
        Возвращает True, если всё ок, False если не удалось перевернуть.
        """
        if (
            signal_side == "Buy"
            and self.current_side == "Sell"
            and self.current_qty > 0
        ):
            close_order_id = self.place_order(
                symbol,
                "Buy",
                self.current_qty,
                limit_price,
            )
            if close_order_id:
                logger.info(
                    f"🔄 Переворот Short → Long. "
                    f"Закрыли {self.current_qty} {symbol}"
                )
                self.current_side = None
                self.current_qty = 0
                self.entries = 0
            else:
                logger.error("❌ Не удалось перевернуть позицию")
                return False

        if (
            signal_side == "Sell"
            and self.current_side == "Buy"
            and self.current_qty > 0
        ):
            close_order_id = self.place_order(
                symbol,
                "Sell",
                self.current_qty,
                limit_price,
            )
            if close_order_id:
                logger.info(
                    f"🔄 Переворот Long → Short. "
                    f"Закрыли {self.current_qty} {symbol}"
                )
                self.current_side = None
                self.current_qty = 0
                self.entries = 0
            else:
                logger.error("❌ Не удалось перевернуть позицию")
                return False

        return True

    def check_entries_limit(
        self,
        signal_side: str,
    ) -> bool:
        """
        Проверяем, не достигли ли мы лимита входов (entries).
        Если side совпадает с self.current_side и self.entries >= max_entries,
        отказываемся.
        """
        if self.current_side == signal_side and self.entries >= self.max_entries:
            logger.warning(
                f"🔔 Достигнут лимит ордеров {self.max_entries} для {self.current_side}."
            )
            return False
        return True

    def place_and_update(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
    ) -> Optional[str]:
        """
        Размещаем новый лимитный ордер, ставим стоп-лосс,
        обновляем локальные переменные (current_side, current_qty, entries).
        Возвращаем order_id или None.
        """
        order_id = self.place_order(
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
        )
        if order_id:
            instruments = self.prepare_instruments(symbol)

            self.set_stop_loss(
                symbol=symbol,
                side=side,
                entry_price=price,
                price_decimals=instruments["price_decimals"],
            )
            logger.info(f"✅ Открыли {side} {qty} {symbol} по {price}")

            # Обновляем локальные переменные
            if self.current_side is None:
                self.current_side = side
                self.current_qty = qty
                self.entries = 1
            elif self.current_side == side:
                self.current_qty += qty
                self.entries += 1
            else:
                # Редкий случай, если мы чего-то пропустили,
                # но с логикой переворота выше вряд ли бывает
                self.current_side = side
                self.current_qty = qty
                self.entries = 1

            return order_id
        else:
            logger.error("⚠️ Не удалось разместить ордер на вход")
            return None

    def execute_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        limit_price: float,
    ) -> Optional[str]:
        # 1) готовим qty и price
        qty_aligned, price_aligned = self.prepare_trade_params(
            symbol,
            side,
            qty,
            limit_price,
        )
        if qty_aligned is None:
            return None

        # 2) синхронизируем текущее состояние
        self.sync_position_with_bybit(symbol)

        # 3) переворот, если нужно
        if not self.handle_reversal_if_needed(
            symbol,
            side,
            price_aligned,
        ):
            return None

        # 4) проверка entries
        if not self.check_entries_limit(side):
            return None

        # 5) размещаем новый ордер, устанавливаем SL, обновляем лок. переменные
        order_id = self.place_and_update(
            symbol,
            side,
            qty_aligned,
            price_aligned,
        )
        return order_id

    def wait_for_fill_and_set_sl(
        self,
        order_id: int | str,
        signal: TradingViewSignal,
    ):
        """
        Фоновая задача:
        1) Ждём, пока лимитный ордер исполнится
        2) Ставим стоп-лосс
        """

        filled = False
        max_attempts = 100  # сколько раз проверять (или ставим таймаут по времени)
        attempt = 0

        instruments = self.prepare_instruments(signal.symbol)

        while not filled and attempt < max_attempts:
            time.sleep(15)  # каждые 15 секунд
            order_status = self.get_order_status(
                order_id=order_id,
                symbol=signal.symbol,
            )

            # order_status может быть 'Filled', 'PartiallyFilled', 'Cancelled', ...
            if order_status == "Filled":
                logger.info(f"Ордер {order_id} исполнен! Ставим стоп-лосс.")
                self.set_stop_loss(
                    symbol=signal.symbol,
                    side=signal.side,
                    entry_price=signal.price,
                    price_decimals=instruments["price_decimals"],
                )
                filled = True
            elif order_status in ["Cancelled", "Rejected"]:
                logger.warning(f"Ордер {order_id} отменён / отклонён, SL не ставим.")
                break
            attempt += 1

        if not filled:
            logger.warning(f"Ордер {order_id} не исполнился за время ожидания.")
