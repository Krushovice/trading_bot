import decimal
import os
import time

from bot.api import Bybit
from bot.trade_logic import Bot

from dotenv import load_dotenv

load_dotenv()

bot = Bot()
bybit = Bybit()


def main():

    load_dotenv()

    data = bybit.get_historical_data()
    data_with_indicators = bot.calculate_indicators(data)

    signal = bot.generate_signal(data)

    print(f"Сгенерированный сигнал: {signal}")


if __name__ == "__main__":

    main()
