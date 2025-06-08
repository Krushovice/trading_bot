import time
from typing import Optional

from utils import align_to_step, setup_logger

from .bybit import Bybit


logger = setup_logger(__name__)


class TradeService(Bybit):
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
        1) Запрашиваем фильтры инструмента (min_qty, tick_size, qty_step).
        2) Выравниваем qty к шагу (и сравниваем с min_qty).
        3) Выравниваем limit_price к шагу tick_size с учётом того, чтобы остаться мейкером.
        4) Если цена пересекает стакан (best_bid/best_ask), двигаем на 1 тик.
        Возвращаем (qty_aligned, price_aligned, tick_size) или None.
        """
        inst = self.get_instruments_info(symbol)
        if inst is None:
            return None

        # 2.a) Выравниваем qty под шаг и минимум
        qty_aligned = max(
            align_to_step(
                value=qty,
                step=inst["qty_step"],
                round_down=True,
            ),
            inst["min_qty"],
        )

        # 2.b) Выравниваем price (limit_price) под tick_size
        #      Для buy — округляем вниз, для sell — вверх
        round_down = side.lower() == "buy"
        price_aligned = align_to_step(
            value=price,
            step=inst["tick_size"],
            round_down=round_down,
        )

        # 3) Корректируем цену, чтобы остаться мейкером: смотрим текущие best_bid/best_ask
        best = self.get_best_bid_ask(symbol)
        if not best:
            return None
        best_bid, best_ask = best

        if side.lower() == "buy":
            # Если выровненная цена выше или равна лучшему аску — сдвигаем вниз
            if price_aligned >= best_ask:
                adjusted = best_ask - inst["tick_size"]
                price_aligned = align_to_step(
                    value=adjusted,
                    step=inst["tick_size"],
                    round_down=True,
                )
                logger.info(
                    "▶ Buy align: заявленная %.8f пересекла best_ask %.8f → "
                    "сдвигаем на %.8f → price=%.8f",
                    price,
                    best_ask,
                    inst["tick_size"],
                    price_aligned,
                )

        # Если выровненная цена ниже или равна лучшему биду — сдвигаем вверх
        elif price_aligned <= best_bid:
            adjusted = best_bid + inst["tick_size"]
            price_aligned = align_to_step(
                value=adjusted,
                step=inst["tick_size"],
                round_down=False,
            )
            logger.info(
                "▶ Sell align: заявленная %.8f пересекла best_bid %.8f → "
                "сдвигаем на %.8f → price=%.8f",
                price,
                best_bid,
                inst["tick_size"],
                price_aligned,
            )

        # 4) Возвращаем готовые величины: qty_aligned, price_aligned, tick_size
        return qty_aligned, price_aligned, inst["tick_size"]

    def execute_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
    ) -> Optional[str]:
        """
        1) Приводим qty и price к шагам
        2) Отправляем лимитный ордер
        3) Возвращаем order_id для фона (SL)
        """
        current_price = self.get_last_price(symbol=symbol)
        if current_price is None:
            logger.error(
                "Не удалось получить текущую цену для %s, прерываем trade", symbol
            )
            return None
        aligned = self._align_order(
            symbol=symbol,
            side=side,
            qty=qty,
            price=current_price,
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

        # Передаём в фоновую задачу order_id
        return order_id

    def wait_for_fill_and_set_sl(
        self,
        order_id: str,
        symbol: str,
        side: str,
    ):
        """
        1) Проверяем статус ордера максимум 25 раз с паузой ~5 секунд.
        2) Если статус стал "Filled" → вызываем set_stop_loss(symbol, side, instruments).
        3) Если за 25 итераций ордер не заполнен → отменяем его через API.
        """

        # Подготовка: получаем тот же словарь instruments, что и в _align_order
        inst = self.get_instruments_info(symbol)
        if inst is None:
            logger.error("Не удалось получить фильтры инструмента для SL")
            return

        max_checks = 25
        sleep_seconds = 5

        for i in range(max_checks):
            status = self.get_order_status(
                order_id=order_id,
                symbol=symbol,
            )
            if status == "Filled":
                logger.info(
                    "Ордер %s исполнен → выставляем SL",
                    order_id,
                )
                # Ставим стоп-лосс, передав instruments (там есть tick_size)
                self.set_stop_loss(
                    symbol=symbol,
                    side=side,
                    instruments=inst,
                )
                return
            if status in ("Cancelled", "Rejected"):
                logger.warning(
                    "Ордер %s отменён/отклонён, SL не ставим",
                    order_id,
                )
                return

            time.sleep(sleep_seconds)

        # Если вышли из цикла, значит ордер всё ещё не исполнился → надо отменить
        try:
            cancel_resp = self.client.cancel_order(
                category=self.category,
                symbol=symbol,
                orderId=order_id,
            )
            if cancel_resp.get("retCode") == 0:
                logger.info(
                    "Ордер %s не исполнился за %s попыток → отменён",
                    order_id,
                    max_checks,
                )
            else:
                logger.error(
                    "Ошибка отмены ордера %s: %s",
                    order_id,
                    cancel_resp.get("retMsg"),
                )
        except Exception as e:
            logger.error(
                "Bybit cancel_order exception: %s",
                e,
                exc_info=True,
            )
