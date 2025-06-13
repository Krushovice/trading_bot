import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from alarm_bot.bot import bot
from core.config import settings
from utils.logger import log_cleanup_loop, setup_logger


logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Этот генератор вызывается при старте и завершении приложения.
    Внутри запускаем фоновый таск log_cleanup_loop и отменяем его при shutdown.
    Устанавливаем webhook дял бота и удаляем его при shutdown
    """

    webhook_url = settings.api_prefix.bot_webhook_url

    try:
        result = await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.bot.secret,
            drop_pending_updates=True,
        )
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
