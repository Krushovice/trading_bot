from typing import Optional, Tuple

from pybit.unified_trading import HTTP

from core.config import settings
from utils import align_to_step, setup_logger


logger = setup_logger(__name__)


class Bybit:
    def __init__(self, use_testnet: bool = False):
        logger.info("Bybit: авторизация выполнена")
        self.category = "linear"
        self.stop_loss_pct = float(settings.bybit_api.sl_pct)
        # fmt: off
        self.client = HTTP(
            api_key=(
                settings.bybit_api.test_key
                if use_testnet
                else settings.bybit_api.key
            ),
            api_secret=(
                settings.bybit_api.test_secret
                if use_testnet
                else settings.bybit_api.secret
            ),
            timeout=30,
            testnet=use_testnet,
        )

    # fmt: on

    def get_instruments_info(
        self,
        symbol: str,
    ) -> Optional[dict[str, float]]:
        """
        Запрашиваем информацию об инструментах. Возвращаем словарь с ключами:
          - min_qty (минимальный размер лота)
          - tick_size (шаг цены)
          - qty_step (шаг количества)
          - price_decimals (количество знаков после запятой для цены)
        В случае любой ошибки возвращаем None.
        """
        try:
            resp = self.client.get_instruments_info(
                symbol=symbol,
                category=self.category,
            )
            if resp["retCode"] != 0 or not resp.get("result", {}).get("list"):
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

            return {
                "min_qty": min_qty,
                "tick_size": tick_size,
                "qty_step": qty_step,
                "price_decimals": price_decimals,
            }

        except Exception as e:
            logger.error(
                "Ошибка get_instruments_info: %s",
                e,
                exc_info=True,
            )
            return None

    def get_best_bid_ask(
        self,
        symbol: str,
    ) -> Optional[Tuple[float, float]]:
        """
        Берём текущие лучшие цены bid1 и ask1 через get_tickers.
        Возвращаем (best_bid, best_ask) или None при ошибке.
        """
        try:
            resp = self.client.get_tickers(
                category=self.category,
                symbol=symbol,
            )
            if resp["retCode"] != 0 or not resp.get("result", {}).get("list"):
                logger.error(
                    "Bybit get_tickers error: %s",
                    resp.get("retMsg"),
                )
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
        1) Принимаем уже выровненные qty и price (align сделан в _align_order).
        2) Посылаем лимитный ордер с timeInForce="PostOnly".
        3) Если retCode==0 → возвращаем orderId, иначе None.
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
            if resp.get("retCode") == 0:
                order_id = resp["result"]["orderId"]
                logger.info(
                    "Лимитный PostOnly %s: %s %s @ %s",
                    side,
                    qty,
                    symbol,
                    price,
                )
                return order_id
            else:
                logger.error(
                    "Bybit place_order error: %s",
                    resp.get("retMsg"),
                )
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
            if resp["retCode"] == 0 and resp.get("result", {}).get("list"):
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

    def get_last_price(
        self,
        symbol: str,
    ) -> float | None:
        """
        Возвращает последнюю цену (LastPrice) для данного символа.
        Если что-то пошло не так, вернёт None.
        """
        try:
            resp = self.client.get_tickers(
                category=self.category,
                symbol=symbol,
            )
            if resp.get("retCode") != 0 or not resp.get("result", {}).get("list"):
                logger.error(
                    "Bybit get_last_price error: %s",
                    resp.get("retMsg"),
                )
                return None
            ticker = resp["result"]["list"][0]
            return float(ticker["lastPrice"])
        except Exception as e:
            logger.error(
                "Bybit get_last_price exception: %s",
                e,
            )
            return None

    def set_stop_loss(
        self,
        symbol: str,
        side: str,
        instruments: dict[str, float],
    ) -> None:
        """
        Ставим стоп-лосс по самой актуальной цене (LastPrice):
          • Для Buy → SL < base_price.
          • Для Sell → SL > base_price.
        1) Запрашиваем base_price = get_last_price(symbol).
        2) raw_sl = base_price * (1 -/+ stop_loss_pct).
        3) Округляем через align_to_step. Если округление нарушает условие (SL ≥ base_price для Buy
           или SL ≤ base_price для Sell), сдвигаем на один тик.
        4) Вызываем set_trading_stop; логируем результат.
        """
        tick_size = instruments["tick_size"]

        base_price = self.get_last_price(symbol)
        if base_price is None:
            logger.error(
                "Не удалось получить текущую цену для %s",
                symbol,
            )
            return

        if side.lower() == "buy":
            raw_sl = base_price * (1 - self.stop_loss_pct / 100)
            aligned_sl = align_to_step(
                value=raw_sl,
                step=tick_size,
                round_down=True,
            )
            if aligned_sl >= base_price:
                aligned_sl = align_to_step(
                    value=base_price - tick_size,
                    step=tick_size,
                    round_down=True,
                )

        else:  # sell
            raw_sl = base_price * (1 + self.stop_loss_pct / 100)
            aligned_sl = align_to_step(
                value=raw_sl,
                step=tick_size,
                round_down=False,
            )
            if aligned_sl <= base_price:
                aligned_sl = align_to_step(
                    value=base_price + tick_size,
                    step=tick_size,
                    round_down=False,
                )

        try:
            resp = self.client.set_trading_stop(
                category=self.category,
                symbol=symbol,
                stopLoss=str(aligned_sl),
                positionIdx=0,
                basePrice=str(base_price),
                stopLossTriggerType="LastPrice",
            )
            if resp.get("retCode") == 0:
                logger.info(
                    "SL установлен для %s: %s",
                    symbol,
                    aligned_sl,
                )
            else:
                logger.error(
                    "Bybit set_stop_loss error: %s",
                    resp.get("retMsg"),
                )

        except Exception as e:
            logger.error(
                "Bybit set_stop_loss exception: %s",
                e,
                exc_info=True,
            )
