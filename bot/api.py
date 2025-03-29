import os
import uuid
import inspect

import pandas as pd
from pybit.unified_trading import HTTP, AccountHTTP, MarketHTTP, TradeHTTP
from pybit import exceptions

from . import setup_logger

logger = setup_logger(__name__)


class Bybit:
    def __init__(self):
        logger.info(f"{os.getenv('NAME', 'Anon')} Bybit auth logged")

        self.position_id = str(uuid.uuid4())
        self.symbol = os.getenv("SYMBOL")
        self.category = "linear"
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PERCENT", 3.0))
        self.timeframe = os.getenv("TIMEFRAME", "5")
        self.limit = int(os.getenv("LIMIT", "100"))

        self.params = dict(
            api_key=os.getenv("API_KEY"),
            api_secret=os.getenv("API_SECRET"),
            timeout=30,
        )
        self.client = HTTP(**self.params)

        instrument_info = self.get_instruments_info()
        if instrument_info:
            self.price_decimals, self.qty_decimals, self.min_qty = instrument_info
        else:
            self.price_decimals, self.qty_decimals, self.min_qty = 4, 3, 0.001

    def check_permissions(self):
        try:
            self.client.get_wallet_balance()
        except Exception as e:
            logger.error(e)

    def get_historical_data(self):
        args = dict(
            category=self.category,
            symbol=self.symbol,
            interval=self.timeframe,
            limit=self.limit,
        )

        response = self.client.get_kline(**args)
        if response["retCode"] == 0:
            klines = response["result"]["list"]
            if klines:
                klines.reverse()  # от старых к новым
                df = pd.DataFrame(
                    klines,
                    columns=[
                        "timestamp",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "turnover",
                    ],
                )
                return df.astype(float)
            else:
                logger.error(f"No kline data returned for {self.symbol}.")
        else:
            logger.error(response["retMsg"])
        return pd.DataFrame()


    def get_instruments_info(self):
        try:
            response = self.client.get_instruments_info(
                symbol=self.symbol,
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

    def get_symbol_price(self):
        try:
            response = self.client.get_tickers(
                category=self.category,
                symbol=self.symbol,
            )
            if response["retCode"] == 0:
                symbols = response["result"]["list"]
                return float(symbols[0]["ask1Price"])
            else:
                logger.error(response["retMsg"])
        except Exception as e:
            logger.error(e)

    def place_order(self, side, qty):
        try:
            response = self.client.place_order(
                category=self.category,
                symbol=self.symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC",
            )
            if response["retCode"] == 0:
                logger.info(f"Ордер успешно размещён: {side} {qty} {self.symbol}")
                return response["result"]["orderId"]
            else:
                logger.error(f"Ошибка API при размещении ордера: {response['retMsg']}")

        except Exception as e:
            logger.error(f"Ошибка API Bybit при размещении ордера: {e}", exc_info=True)


    def get_open_positions(self):
        try:
            response = self.client.get_positions(
                category=self.category,
                symbol=self.symbol,
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

    def set_stop_loss(self, side, entry_price):
        if side == "Buy":
            stop_loss_price = round(
                entry_price * (1 - self.stop_loss_pct / 100), self.price_decimals
            )
        else:
            stop_loss_price = round(
                entry_price * (1 + self.stop_loss_pct / 100), self.price_decimals
            )

        try:
            response = self.client.set_trading_stop(
                category=self.category,
                symbol=self.symbol,
                stopLoss=str(stop_loss_price),
                positionIdx=0,
            )
            if response["retCode"] == 0:
                logger.info(f"Stop-loss успешно установлен: {stop_loss_price}")
            else:
                logger.error(f"Ошибка установки Stop-loss: {response['retMsg']}")
        except Exception as e:
            logger.error(e)
