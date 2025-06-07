import asyncio
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
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from alarm_bot.instruments import check_for_admin
from alarm_bot.keyboards import get_logs_kb
from utils.logger import setup_logger


logger = setup_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

ADMIN_ID = int(os.getenv("ADMIN_ID"))
SECRET_KEY = os.getenv("MY_SECRET_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
ALERT_PATH = os.getenv("ALERT_PATH")


dp = Dispatcher()

bot = Bot(
    token="7945158776:AAF9KOuwtqrFayBaXVuHcEUs7QdUaxZ_0sw",
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

bot_app = FastAPI(
    prefix=BOT_PREFIX,
)


@bot_app.get("")
async def root():
    return {"message": "FastAPI + Aiogram (webhook) запущены"}


@bot_app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    # Проверяем, что переданный X-Telegram-Bot-Api-Secret-Token совпадает с HOOK_SECRET
    if x_telegram_bot_api_secret_token != os.getenv("HOOK_SECRET"):
        raise HTTPException(
            status_code=403,
            detail="Forbidden",
        )
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

    logs_path = os.path.join(BASE_DIR, "logs")
    logs = os.listdir(logs_path)

    if os.path.exists(logs_path) and len(logs) > 0:
        for log in logs:
            if not os.path.getsize(f"{logs_path}/{log}") == 0:
                await call.message.answer_document(
                    FSInputFile(
                        path=f"{logs_path}/{log}",
                    )
                )
    else:
        await call.message.answer("Логи за сегодня не найдены.")


@dp.callback_query(F.data == "back")
async def handle_back_button(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        text="Hello, Krushovice!",
        reply_markup=get_logs_kb(),
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
