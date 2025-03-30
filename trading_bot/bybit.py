import os

from pybit.unified_trading import HTTP

from . import setup_logger

logger = setup_logger(__name__)


class Bybit:
    def __init__(self):
        logger.info(f"{os.getenv('NAME', 'Anon')} Bybit auth logged")

        self.category = "linear"
        self.stop_loss_pct = 3.0

        self.params = dict(
            api_key=os.getenv("API_KEY"),
            api_secret=os.getenv("API_SECRET"),
            timeout=30,
        )
        self.client = HTTP(**self.params)

    def check_permissions(self):
        try:
            self.client.get_wallet_balance()
        except Exception as e:
            logger.error(e)

    def get_instruments_info(self, symbol):
        try:
            response = self.client.get_instruments_info(
                symbol=symbol,
                category=self.category,
            )
            if response["retCode"] == 0 and response["result"]["list"]:
                info = response["result"]["list"][0]
                price_decimals = int(info.get("priceScale", 4))
                qty_decimals = len(str(info["lotSizeFilter"]["qtyStep"]))
                min_qty = float(info["lotSizeFilter"]["minOrderQty"])
                return price_decimals, qty_decimals, min_qty
            else:
                logger.error(response["retMsg"])
        except Exception as e:
            logger.error(e)
        return None

    def get_symbol_price(self, symbol):
        try:
            response = self.client.get_tickers(
                category=self.category,
                symbol=symbol,
            )
            if response["retCode"] == 0:
                symbols = response["result"]["list"]
                return float(symbols[0]["ask1Price"])
            else:
                logger.error(response["retMsg"])
        except Exception as e:
            logger.error(e)

    def place_order(self, symbol, side, qty, price):
        try:
            response = self.client.place_order(
                category=self.category,
                symbol=symbol,
                side=side,
                orderType="Limit",
                qty=str(qty),
                price=str(price),
                timeInForce="PostOnly",
            )
            if response["retCode"] == 0:
                logger.info(
                    f"Лимитный ордер размещён: {side} {qty} {symbol} по цене {price}"
                )
                return response["result"]["orderId"]
            else:
                logger.error(
                    f"Ошибка API при размещении лимитного ордера: {response['retMsg']}"
                )

        except Exception as e:
            logger.error(
                f"Ошибка API Bybit при размещении лимитного ордера: {e}", exc_info=True
            )

    def get_open_positions(self, symbol):
        try:
            response = self.client.get_positions(
                category=self.category,
                symbol=symbol,
            )
            if response["retCode"] == 0:
                return [
                    p for p in response["result"]["list"] if float(p.get("size", 0)) > 0
                ]
            else:
                logger.error(response["retMsg"])
        except Exception as e:
            logger.error(e)

        return []

    def set_stop_loss(self, symbol, side, entry_price, price_decimals):
        if side == "Buy":
            stop_loss_price = round(
                entry_price * (1 - self.stop_loss_pct / 100), price_decimals
            )
        else:
            stop_loss_price = round(
                entry_price * (1 + self.stop_loss_pct / 100), price_decimals
            )

        try:
            response = self.client.set_trading_stop(
                category=self.category,
                symbol=symbol,
                stopLoss=str(stop_loss_price),
                positionIdx=0,
            )
            if response["retCode"] == 0:
                logger.info(f"Stop-loss для {symbol} установлен: {stop_loss_price}")
            else:
                logger.error(f"Ошибка установки Stop-loss: {response['retMsg']}")
        except Exception as e:
            logger.error(e)
