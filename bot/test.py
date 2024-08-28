from Bybit import Bybit

trade = Bybit()


def main():
    balance = trade.check_permissions()
    print(balance)


if __name__ == "__main__":
    main()
