import asyncio

from fastapi import FastAPI

from utils.logger import log_cleanup_loop


async def lifespan(app: FastAPI):
    """
    Этот генератор вызывается при старте и завершении приложения.
    Внутри запускаем фоновый таск log_cleanup_loop и отменяем его при shutdown.
    """
    cleanup_task = asyncio.create_task(log_cleanup_loop())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
