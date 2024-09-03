import logging

import os
import sys
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_logger(module_name):
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.ERROR)
    filename = os.path.splitext(os.path.basename(module_name))[0]

    # Проверяем, был ли уже добавлен обработчик
    if not logger.handlers:
        # Добавляем обработчик для записи в файл
        file_handler = RotatingFileHandler(
            f"{BASE_DIR}/logs/{filename}.log",
            maxBytes=100000,
            backupCount=5,
            encoding="utf-8",  # Добавляем поддержку UTF-8
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Добавляем обработчик для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)  # Установите уровень лога для консоли
        console_handler.setStream(
            sys.stdout
        )  # Используем sys.stdout для поддержки UTF-8
        logger.addHandler(console_handler)

    return logger
