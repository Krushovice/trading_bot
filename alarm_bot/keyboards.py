from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
