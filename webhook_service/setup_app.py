from core.config import settings
from fastapi import FastAPI
from fastapi.middleware import Middleware

from alarm_bot.bot import bot_app

from .lifespan import lifespan


def setup_app(
    middleware: list[Middleware],
) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        middleware=middleware,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Подключаем bot_app
    app.mount(
        settings.api_prefix.bot,
        bot_app,
    )
    return app
