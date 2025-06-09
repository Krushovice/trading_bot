import pytest
from aiogram import Bot

from aiogram.types import Message, User, Chat, Update

from alarm_bot.bot import dp, bot
from alarm_bot.keyboards import get_logs_kb
from core.config import settings

admin_id = settings.bot.admin


@pytest.mark.asyncio
async def test_command_start_handler(monkeypatch):
    # Создаём фейковое сообщение от ADMIN_ID
    user = User(
        id=admin_id,
        is_bot=False,
        first_name="Test",
        username="test",
    )
    chat = Chat(id=admin_id, type="private")
    message = Message(
        message_id=1,
        date=0,
        text="/start",
        from_user=user,
        chat=chat,
    )

    sent = {}

    # 2) Подменяем Bot.__call__, чтобы любые TelegramMethod не ушли в сеть,
    #    а мы могли вытащить параметры из объекта метода.
    sent = {}

    async def fake_call(self, method, *args, **kwargs):
        # здесь method — это экземпляр SendMessage, SendPhoto и т.д.
        if hasattr(method, "chat_id"):
            sent["chat_id"] = method.chat_id
            sent["text"] = method.text
            sent["reply_markup"] = getattr(method, "reply_markup", None)
        # возвращаем тот же метод (или можно вернуть фейковый ответ)
        return method

    monkeypatch.setattr(Bot, "__call__", fake_call)

    update = Update(update_id=1, message=message)

    # 3) Прокидываем апдейт в диспетчер
    # используем самый высокоуровневый entrypoint, чтобы __call__ отработал:
    # feed_update НЕ вызывает __call__, а _process_update вызывает.
    await dp._process_update(bot=bot, update=update)

    # 4) Проверяем, что fake_call сработал
    assert sent["chat_id"] == admin_id
    assert "Hello, Krushovice" in sent["text"]
    assert sent["reply_markup"] == get_logs_kb()
