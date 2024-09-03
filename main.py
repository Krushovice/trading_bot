from pybit import exceptions
from bot import Bot, setup_logger


from dotenv import load_dotenv

logger = setup_logger(__name__)

load_dotenv()


if __name__ == "__main__":
    try:
        Bot().run()
    except KeyboardInterrupt as e:
        logger.debug("Бот остановлен вручную!")
    except exceptions.InvalidRequestError as e:
        logger.debug(str(e))
    except exceptions.FailedRequestError as e:
        logger.debug(str(e))
    except Exception as e:
        logger.error(str(e))
