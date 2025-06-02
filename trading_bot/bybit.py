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
        # Процент стоп-лосса (можно менять через ENV)
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
        Возвращаем:
          (min_qty, tick_size, qty_step, price_decimals)
        или None, если что-то не так.
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

    def get_best_bid_ask(self, symbol: str) -> Optional[Tuple[float, float]]:
        """
        Берём текущие лучшие цены bid1 и ask1 через get_tickers.
        Возвращаем (best_bid, best_ask) или None при ошибке.
        """
        try:
            resp = self.client.get_tickers(
                category=self.category,
                symbol=symbol,
            )
            if resp["retCode"] != 0 or not resp["result"]["list"]:
                logger.error("Bybit get_tickers error: %s", resp.get("retMsg"))
                return None
            ticker = resp["result"]["list"][0]
            best_bid = float(ticker["bid1Price"])
            best_ask = float(ticker["ask1Price"])
            return best_bid, best_ask
        except Exception as e:
            logger.error(
                "Ошибка get_best_bid_ask: %s",
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
        Размещает лимитный ордер как PostOnly.
        Чтобы избежать мгновенной отмены, проверяем best_bid/ask и,
        если пришедшая цена пересекает стакан, «подвигаем» её на 1 тик.
        """
        # 1. Узнаём фильтры инструмента, чтобы правильно округлить qty и price
        inst = self.get_instruments_info(symbol)
        if not inst:
            return None
        min_qty, tick_size, qty_step, _ = inst

        # 2. Приводим qty к шагу и min_qty
        qty_aligned = max(align_to_step(qty, qty_step), min_qty)

        # 3. Приводим price к шагу (округляем вниз для Buy, вверх для Sell)
        round_down = side.lower() == "buy"
        price_aligned = align_to_step(
            price,
            tick_size,
            round_down=round_down,
        )

        # 4. Получаем текущие best_bid и best_ask
        best = self.get_best_bid_ask(symbol)
        if not best:
            return None
        best_bid, best_ask = best

        # 5. Если ордер пересечёт стакан → сдвигаем его на 1 тик
        if side.lower() == "buy":
            if price_aligned >= best_ask:
                # Чтобы точно быть мейкером, ставим price = best_ask - tick_size
                adjusted = best_ask - tick_size
                price_aligned = align_to_step(
                    adjusted,
                    tick_size,
                    round_down=True,
                )
                logger.info(
                    "▶ Buy-PostOnly: ваша цена %.8f пересекла best_ask %.8f → "
                    "сдвигаем на %s → price=%.8f",
                    price,
                    best_ask,
                    tick_size,
                    price_aligned,
                )
        elif price_aligned <= best_bid:
            # Чтобы остаться мейкером, ставим price = best_bid + tick_size
            adjusted = best_bid + tick_size
            price_aligned = align_to_step(
                adjusted,
                tick_size,
                round_down=False,
            )
            logger.info(
                "▶ Sell-PostOnly: ваша цена %.8f пересекла best_bid %.8f → "
                "сдвигаем на %s → price=%.8f",
                price,
                best_bid,
                tick_size,
                price_aligned,
            )

        # 6. Наконец, размещаем PostOnly-ордер
        try:
            resp = self.client.place_order(
                category=self.category,
                symbol=symbol,
                side=side.capitalize(),
                orderType="Limit",
                qty=str(qty_aligned),
                price=str(price_aligned),
                timeInForce="PostOnly",
            )
            if resp["retCode"] == 0:
                logger.info(
                    "Лимитный PostOnly %s: %s %s @ %s",
                    side,
                    qty_aligned,
                    symbol,
                    price_aligned,
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
        Считаем SL относительно entry_price:
         - Для LONG → SL = entry_price * (1 − stop_loss_pct/100) (округляем вниз)
         - Для SHORT → SL = entry_price * (1 + stop_loss_pct/100) (округляем вверх)

        Передаём basePrice = entry_price, чтобы Bybit не ругался на перекрытие с рыночной ценой.
        """
        if side.lower() == "buy":
            raw_sl = entry_price * (1 - self.stop_loss_pct / 100)
            sl_price = align_to_step(
                raw_sl,
                tick_size,
                round_down=True,
            )
        else:
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
                basePrice=str(entry_price),
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
