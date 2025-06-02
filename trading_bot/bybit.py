# trading_bot/bybit.py
import os
from typing import Optional, Tuple

from pybit.unified_trading import HTTP

from utils import align_to_step, setup_logger


logger = setup_logger(__name__)


class Bybit:
    def __init__(self):
        logger.info("Bybit: авторизация выполнена")
        self.category = "linear"
        # Процент стоп-лосса (если нужно менять, можно выставлять через ENV)
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "3.0"))  # 3%

        self.client = HTTP(
            api_key=os.getenv("API_KEY"),
            api_secret=os.getenv("API_SECRET"),
            timeout=30,
        )

    def get_instruments_info(
        self, symbol: str
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Получаем фильтры инструмента:
          (min_qty, tick_size, qty_step, price_decimals)
        Возвращаем None, если что-то пошло не так.
        """
        try:
            resp = self.client.get_instruments_info(
                symbol=symbol, category=self.category
            )
            if resp["retCode"] != 0 or not resp["result"]["list"]:
                logger.error(
                    "Bybit get_instruments_info error: %s",
                    resp.get("retMsg"),
                )
                return None

            info = resp["result"]["list"][0]
            min_qty = float(info["lotSizeFilter"]["minOrderQty"])
            tick_size = float(info["priceFilter"]["tickSize"])
            qty_step = float(info["lotSizeFilter"]["qtyStep"])
            price_decimals = int(info.get("priceScale", 4))
            return min_qty, tick_size, qty_step, price_decimals

        except Exception as e:
            logger.error(
                "Ошибка get_instruments_info: %s",
                e,
                exc_info=True,
            )
            return None

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
    ) -> Optional[str]:
        """
        Размещает лимитный ордер.
        Возвращает orderId либо None (в случае ошибки).
        """
        try:
            resp = self.client.place_order(
                category=self.category,
                symbol=symbol,
                side=side.capitalize(),
                orderType="Limit",
                qty=str(qty),
                price=str(price),
                timeInForce="PostOnly",
            )
            if resp["retCode"] == 0:
                logger.info(
                    "Лимитный ордер %s: %s %s @ %s",
                    side,
                    qty,
                    symbol,
                    price,
                )
                return resp["result"]["orderId"]
            else:
                logger.error("Place order error: %s", resp.get("retMsg"))
                return None

        except Exception as e:
            logger.error(
                "Bybit place_order exception: %s",
                e,
                exc_info=True,
            )
            return None

    def get_order_status(
        self,
        symbol: str,
        order_id: str,
    ) -> Optional[str]:
        """
        Получаем статус ордера: "Filled", "New", "PartiallyFilled", "Cancelled" и т. д.
        """
        try:
            resp = self.client.get_open_orders(
                category=self.category,
                symbol=symbol,
                orderId=order_id,
            )
            if resp["retCode"] == 0 and resp["result"]["list"]:
                return resp["result"]["list"][0].get("orderStatus")
            else:
                logger.error(
                    "get_order_status error: %s",
                    resp.get("retMsg"),
                )
                return None

        except Exception as e:
            logger.error(
                "Exception get_order_status: %s",
                e,
                exc_info=True,
            )
            return None

    def set_stop_loss(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        tick_size: float,
    ) -> None:
        """
        Считаем Stop-Loss относительно цены входа (entry_price):
         - Для LONG → SL = entry_price * (1 − stop_loss_pct/100) (и выравниваем вниз)
         - Для SHORT → SL = entry_price * (1 + stop_loss_pct/100) (и выравниваем вверх)

        Затем отправляем set_trading_stop, где в качестве basePrice используем entry_price.
        """
        if side.lower() == "buy":
            # Лонг: SL ниже entry
            raw_sl = entry_price * (1 - self.stop_loss_pct / 100)
            sl_price = align_to_step(
                raw_sl,
                tick_size,
                round_down=True,
            )
        else:
            # Шорт: SL выше entry
            raw_sl = entry_price * (1 + self.stop_loss_pct / 100)
            sl_price = align_to_step(
                raw_sl,
                tick_size,
                round_down=False,
            )

        try:
            resp = self.client.set_trading_stop(
                category=self.category,
                symbol=symbol,
                stopLoss=str(sl_price),
                positionIdx=0,
                basePrice=str(entry_price),  # используем цену входа
                stopLossTriggerType="LastPrice",
            )
            if resp.get("retCode") == 0:
                logger.info(
                    "SL установлен для %s: %s",
                    symbol,
                    sl_price,
                )
            else:
                logger.error(
                    "Ошибка установки SL: %s",
                    resp.get("retMsg"),
                )
        except Exception as e:
            logger.error(
                "Exception set_stop_loss: %s",
                e,
                exc_info=True,
            )
