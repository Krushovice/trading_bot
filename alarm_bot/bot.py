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

from utils.logger import setup_logger


BASE_DIR = Path(__file__).resolve().parent

logger = setup_logger(__name__)

dp = Dispatcher()


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
    if tg_id == int(os.getenv("ADMIN_ID")):
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
    bot = Bot(
        token=os.getenv(
            "BOT_TOKEN",
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ),
    )
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by admin")

    except AiogramError as error:
        logger.critical(error)
