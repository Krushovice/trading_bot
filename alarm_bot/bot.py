from datetime import datetime
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import AiogramError
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from fastapi import FastAPI, HTTPException, Request

from utils.logger import setup_logger


logger = setup_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SECRET_KEY = os.getenv("MY_SECRET_KEY")

dp = Dispatcher()

bot = Bot(
    token=os.getenv(
        "BOT_TOKEN",
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    ),
)
alert_app = FastAPI()


@alert_app.post("/alert-critical")
async def alert_critical(request: Request):
    data = await request.json()
    if data.get("key") != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

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


def get_logs_kb() -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        text=f"👀Логи за {datetime.now().date()}",
        callback_data="show_logs",
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    return keyboard


def root_kb() -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        text="🔙На главную",
        callback_data="back",
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    return keyboard


def load_logs():
    pass


def check_for_admin(tg_id: int) -> bool:
    if tg_id == ADMIN_ID:
        return True
    return False


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


async def main() -> None:
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by admin")

    except AiogramError as error:
        logger.critical(error)
