import os
import uuid
from pybit.unified_trading import HTTP, AccountHTTP


session = HTTP(
    api_key="1rBEjCPlECvFYTCPWl",
    api_secret="Y6MTIcKivJtzE80yquYYcrmwY6SOZ0vEMlB4",
)

if __name__ == "__main__":
    res = session.get_tickers(category="linear", symbol="DOGEUSDT")
    print(res)
