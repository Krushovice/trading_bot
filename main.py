import os

from pybit import exceptions
from bot import Bot, setup_logger
from dotenv import load_dotenv
import traceback

# Настройка логгера
logger = setup_logger(__name__)


load_dotenv()

if __name__ == "__main__":
    try:
        # Запуск бота
        bot = Bot(max_usdt_to_spend=os.getenv("CAPITAL"))
        bot.run()
        print("Bot run!")
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную!")
    except exceptions.InvalidRequestError as e:
        logger.error(f"Invalid request error: {str(e)}")
    except exceptions.FailedRequestError as e:
        logger.error(f"Failed request error: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Bot has been stopped.")
