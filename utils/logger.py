from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = os.path.join(BASE_DIR, "logs")


def delete_old_logs(log_dir: str):
    for file in os.listdir(log_dir):
        if file.endswith(".log"):
            os.remove(os.path.join(log_dir, file))


def setup_logger(module_name: str) -> logging.Logger:
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    today_str = datetime.now().strftime("%Y-%m-%d")
    log_filename = (
        f"{os.path.splitext(os.path.basename(module_name))[0]}_{today_str}.log"
    )
    log_path = os.path.join(LOG_DIR, log_filename)

    if not logger.handlers:
        os.makedirs(LOG_DIR, exist_ok=True)
        delete_old_logs(LOG_DIR)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=100_000,
            backupCount=1,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.ERROR)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
