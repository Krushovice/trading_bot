# trading_bot/trade_logic.py
import time
from typing import Optional

from utils import align_to_step, normalize_symbol, setup_logger

from .bybit import Bybit
from .schemas import TradingViewSignal


logger = setup_logger(__name__)


class Bot(Bybit):
    def __init__(self):
        super().__init__()
        # Вся логика торговых решений уже в стратегии TradingView,

    def _align_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
    ) -> Optional[tuple[float, float, float]]:
        """
        Достаём фильтры инструмента и приводим qty/price к шагам:
          возвращаем (qty_aligned, price_aligned, tick_size) или None.
        """
        inst = self.get_instruments_info(symbol)
        if inst is None:
            return None

        min_qty, tick_size, qty_step, _ = inst

        # Количество ≥ min_qty и кратно qty_step
        qty_aligned = max(align_to_step(qty, qty_step), min_qty)

        # Цена: кратна tick_size
        round_down = side.lower() == "buy"
        price_aligned = align_to_step(
            price,
            tick_size,
            round_down=round_down,
        )

        return qty_aligned, price_aligned, tick_size

    def execute_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        limit_price: float,
    ) -> Optional[str]:
        """
        1) Приводим qty и price к шагам
        2) Отправляем лимитный ордер
        3) Возвращаем order_id для фона (SL)
        """
        aligned = self._align_order(
            symbol,
            side,
            qty,
            limit_price,
        )
        if aligned is None:
            return None

        qty_aligned, price_aligned, tick_size = aligned

        order_id = self.place_order(
            symbol=symbol,
            side=side,
            qty=qty_aligned,
            price=price_aligned,
        )
        if not order_id:
            return None

        # Передаём в фоновую задачу: symbol, side, entry_price=price_aligned, tick_size
        return order_id

    def wait_for_fill_and_set_sl(
        self,
        order_id: str,
        signal: TradingViewSignal,
    ):
        """
        Ждём исполнения лимитного ордера (до 100 попыток, pause=5s).
        Если статус "Filled" → ставим SL, где basePrice = entry_price (из сигнала).
        """
        symbol = normalize_symbol(signal.symbol)

        # Получаем entry_price из сигнала (он там же, где limit_price)
        entry_price = signal.price

        # Узнаём tick_size (чтобы посчитать SL). Можно повторно вызвать get_instruments_info:
        inst = self.get_instruments_info(symbol)
        if not inst:
            return
        _, tick_size, _, _ = inst

        for _ in range(100):
            status = self.get_order_status(
                symbol=symbol,
                order_id=order_id,
            )
            if status == "Filled":
                logger.info(
                    "Ордер %s исполнен → выставляем SL",
                    order_id,
                )
                self.set_stop_loss(
                    symbol=symbol,
                    side=signal.side,
                    entry_price=entry_price,
                    tick_size=tick_size,
                )
                return

            if status in ("Cancelled", "Rejected"):
                logger.warning(
                    "Ордер %s отменён/отклонён → SL не ставим",
                    order_id,
                )
                return

            time.sleep(5)

        logger.warning(
            "Ордер %s не успел исполниться за ограниченное время",
            order_id,
        )
