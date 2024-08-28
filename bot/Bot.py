import os
import ta
import numpy as np
import pandas as pd
from time import sleep
from Bybit import Bybit
import logging

logger = logging.getLogger(__name__)


class Bot(Bybit):
    """
    Класс Bot реализует логику торговли, наследуя методы взаимодействия с биржей OKX.
    """

    def __init__(self):
        super(Bot, self).__init__()

        self.timeout = int(os.getenv('TIMEOUT', 60))
        self.timeframe = os.getenv('TIMEFRAME', '1m')
        self.ema_length = int(os.getenv('EMA_LENGTH', '200'))
        self.factor = float(os.getenv('FACTOR', '1.7'))
        self.model = os.getenv('MODEL', 'Buy on enter to OverSell')
        self.dno = self.model == "Buy on enter to OverSell"

    def get_v(self):
        """
        Рассчитывает разницу между закрытием и EMA, а также стандартное отклонение для этой разницы.
        """
        close = self.close_prices(self.symbol, self.timeframe)
        ema = ta.trend.ema_indicator(close, self.ema_length).values
        v = close - ema
        dev = ta.volatility.bollinger_hband(close, self.ema_length, ndev=1) - ema  # Используем стандартное отклонение
        return v, dev

    def is_cross(self):
        """
        Определяет, произошло ли пересечение зоны перекупленности/перепроданности.
        Возвращает:
         0 - если на текущем баре пересечения нет
         1 - сигнал на покупку
        -1 - сигнал на продажу
        """
        v, dev = self.get_v()
        k = -1 if self.dno else 1
        dev_limit = k * dev[-1] * self.factor

        r = 0
        if self.dno and v[-2] < dev_limit and v[-1] > dev_limit:
            r = 1
        elif not self.dno and v[-2] > dev_limit and v[-1] < dev_limit:
            r = -1

        if r != 0:
            logger.info(f"Signal: {r}, v: {v[-1]:.6f}, dev_limit: {dev_limit:.6f}")
        return r

    def check(self):
        """
        Проверка сигналов и постановка ордеров.
        """
        try:
            cross = self.is_cross()

            if cross > 0 and not self.is_position():
                self.place_order('buy')
            elif cross < 0 and self.is_position():
                self.place_order('sell')

        except Exception as e:
            logger.error(str(e))

    def loop(self):
        """
        Цикл проверки.
        """
        while True:
            self.check()
            sleep(self.timeout)

    def run(self):
        """
        Инициализация бота.
        """
        logger.info("The Bot is started!")
        self.check_permissions()
        self.loop()


# Для использования класса
if __name__ == "__main__":
    bot = Bot()
    bot.run()
