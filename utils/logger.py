import asyncio
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = os.path.join(BASE_DIR, "logs")


def delete_old_logs(
    log_dir: str,
    days: int,
):
    """
    Удаляет все .log-файлы в папке log_dir старше `days` дней.
    """
    if not os.path.isdir(log_dir):
        return

    cutoff = datetime.now() - timedelta(days=days)
    for filename in os.listdir(log_dir):
        if not filename.endswith(".log"):
            continue

        file_path = os.path.join(log_dir, filename)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            if mtime < cutoff:
                os.remove(file_path)
        except Exception:
            # На всякий случай игнорируем ошибки доступа
            pass


def setup_logger(module_name: str) -> logging.Logger:
    """
    Создаёт логгер для модуля module_name.
    Не удаляет старые файлы — этим занимается отдельная задача.
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    # Имя файла: <название_модуля>_YYYY-MM-DD.log
    today_str = datetime.now().strftime("%Y-%m-%d")
    module_base = os.path.splitext(os.path.basename(module_name))[0]
    log_filename = f"{module_base}_{today_str}.log"
    log_path = os.path.join(LOG_DIR, log_filename)

    if not logger.handlers:
        os.makedirs(LOG_DIR, exist_ok=True)

        # Файловый обработчик (rotating по 100 KB, 1 backup)
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

        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


async def log_cleanup_loop(days: int = 1):
    """
    Фоновая корутина, которая при старте сразу очищает старые логи,
    затем ждет 24 часа и повторяет.
    """
    while True:
        try:
            delete_old_logs(LOG_DIR, days)
            logging.getLogger(__name__).info(
                f"Deleted .log files older than {days} day(s)."
            )
        except Exception as e:
            logging.getLogger(__name__).error(
                "Error during log cleanup: %s",
                e,
            )

        # Засыпаем ровно на 24 часа
        await asyncio.sleep(24 * 60 * 60)
