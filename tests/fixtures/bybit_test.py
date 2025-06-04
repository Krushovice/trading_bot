from trading_bot.bybit import Bybit


class BybitTest(Bybit):
    def __init__(self):
        super().__init__(use_testnet=True)
