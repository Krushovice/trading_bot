import os
import traceback

from dotenv import load_dotenv
from pybit import exceptions
from bot import Bot, setup_logger
from bot.storage import PositionStorage

# Настройка логгера
logger = setup_logger(__name__)

load_dotenv()

if __name__ == "__main__":
    try:
        storage = PositionStorage()
        bot = Bot(
            max_usdt_to_spend=int(os.getenv("CAPITAL", "10")),
            interval=int(os.getenv("INTERVAL", "300")),
            storage=storage,
        )
        logger.info("Bot started successfully.")
        bot.run()

    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную!")

    except (exceptions.InvalidRequestError, exceptions.FailedRequestError) as e:
        logger.error(f"Bybit API error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        logger.error(traceback.format_exc())

    finally:
        logger.info("Bot has been stopped.")
