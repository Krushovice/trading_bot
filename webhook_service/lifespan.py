import asyncio
from contextlib import asynccontextmanager
import os
from typing import TYPE_CHECKING

from fastapi import FastAPI

from utils.logger import log_cleanup_loop, setup_logger


if TYPE_CHECKING:
    from alarm_bot.bot import bot


logger = setup_logger(__name__)

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST_URL")
BOT_PREFIX = os.getenv("BOT_PREFIX")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
BOT_TOKEN = os.getenv("BOT_TOKEN")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Этот генератор вызывается при старте и завершении приложения.
    Внутри запускаем фоновый таск log_cleanup_loop и отменяем его при shutdown.
    Устанавливаем webhook дял бота и удаляем его при shutdown
    """

    full_path = f"{BOT_PREFIX}{WEBHOOK_PATH}/{BOT_TOKEN}"
    webhook_url = WEBHOOK_HOST.rstrip("/") + full_path

    try:
        result = await bot.set_webhook(webhook_url)
        logger.info(f"set_webhook response: {result}")
    except Exception as e:
        logger.error(f"Failed to set webhook to {webhook_url}: {e}")

    cleanup_task = asyncio.create_task(log_cleanup_loop())

    yield
    cleanup_task.cancel()

    try:
        await cleanup_task
        await bot.delete_webhook()
        logger.info("Bot webhook удалён")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
