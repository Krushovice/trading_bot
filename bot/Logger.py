import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logger(module_name):
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.ERROR)
    filename = os.path.splitext(os.path.basename(module_name))[0]

    # Проверяем, был ли уже добавлен обработчик
    if not logger.handlers:
        # Добавляем обработчик для записи в файл
        file_handler = RotatingFileHandler(
            f"logs/{filename}.log",
            maxBytes=100000,
            backupCount=5,
        )
        formatter = logging.Formatter(
            "%(name)s %(asctime)s %(levelname)s %(filename)s %(funcName)s line %(lineno)d: %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
