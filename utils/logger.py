import logging
from logging.handlers import RotatingFileHandler
import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_logger(module_name):
    logger = logging.getLogger(module_name)
    logger.setLevel(
        logging.DEBUG
    )  # Общий уровень для логгера (управляется handler'ами отдельно)

    filename = os.path.splitext(os.path.basename(module_name))[0]

    if not logger.handlers:
        # Создание директории для логов, если её нет
        log_dir = f"{BASE_DIR}/logs"
        os.makedirs(log_dir, exist_ok=True)

        # Файловый обработчик (только ошибки и выше)
        file_handler = RotatingFileHandler(
            f"{log_dir}/{filename}.log",
            maxBytes=100000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.ERROR)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Консольный обработчик (только INFO)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
