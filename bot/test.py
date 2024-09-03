import os
import uuid
from pybit.unified_trading import HTTP, AccountHTTP


session = HTTP(
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
)

if __name__ == "__main__":
    res = session.get_tickers(category="linear", symbol="DOGEUSDT")
    print(res)
