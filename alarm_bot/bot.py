from datetime import datetime
import os
from pathlib import Path
import traceback

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    Message,
    Update,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from utils.logger import setup_logger

from .instruments import check_for_admin
from .keyboards import get_logs_kb


logger = setup_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent

ADMIN_ID = int(os.getenv("ADMIN_ID"))
SECRET_KEY = os.getenv("MY_SECRET_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
BOT_PREFIX = os.getenv("BOT_PREFIX")
ALERT_PATH = os.getenv("ALERT_PATH")


dp = Dispatcher()

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

bot_app = FastAPI(
    prefix=os.getenv("BOT_PREFIX"),
)


@bot_app.get("")
async def root():
    return {"message": "FastAPI + Aiogram (webhook) запущены"}


@bot_app.post(f"{WEBHOOK_PATH}/{BOT_TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    try:
        await dp.feed_update(
            bot=bot,
            update=update,
        )
    except Exception:
        tb = traceback.format_exc()
        logger.error(
            "Ошибка обработки Telegram Update:\n%s",
            tb,
        )
    return JSONResponse({"ok": True})


@bot_app.post(ALERT_PATH)
async def alert_critical(request: Request):
    data = await request.json()
    if data.get("key") != SECRET_KEY:
        raise HTTPException(
            status_code=403,
            detail="Forbidden",
        )

    error_text = data.get("error")
    if not error_text:
        raise HTTPException(
            status_code=400,
            detail="No error message provided",
        )

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🚨 <b>Критическая ошибка в FastAPI:</b>\n<pre>{error_text}</pre>",
        parse_mode="HTML",
    )

    return {"status": "ok"}


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    admin_check = check_for_admin(message.from_user.id)
    if admin_check:
        await message.answer(
            text="Hello, Krushovice!",
            reply_markup=get_logs_kb(),
        )


@dp.callback_query(F.data == "show_logs")
async def handle_show_logs(call: CallbackQuery):
    await call.answer()

    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(BASE_DIR, "logs", f"bot_{today}.log")

    if os.path.exists(log_path):
        await call.message.answer_document(FSInputFile(log_path))
    else:
        await call.message.answer("Логи за сегодня не найдены.")


@dp.callback_query(F.data == "back")
async def handle_back_button(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        text="Hello, Krushovice!",
        reply_markup=get_logs_kb(),
    )
