import pytest
from aiogram import Bot
from aiogram.types import Update

from alarm_bot import bot
from alarm_bot.keyboards import get_logs_kb


class TestBot:
    @classmethod
    @pytest.mark.asyncio
    async def test_start_handler(cls, update, message):
        # Словарь для проверки вызова
        sent = {}

        async def fake_call(self, method, *args, **kwargs):
            if hasattr(method, "chat_id"):
                sent["chat_id"] = method.chat_id
                sent["text"] = method.text
                sent["reply_markup"] = method.reply_markup
            return method

        # Переопределяем Bot.__call__ только для этого теста
        Bot.__call__ = fake_call

        # Запускаем обработку
        await bot.dp._process_update(bot=bot.bot, update=update)

        # Проверяем результат
        assert sent["chat_id"] == update.message.chat.id
        assert "Hello, Krushovice" in sent["text"]
        assert sent["reply_markup"] == get_logs_kb()

    @classmethod
    @pytest.mark.asyncio
    async def test_logs_callback_handler(
        cls,
        tmp_path,
        callback_query,
        monkeypatch,
    ):
        # tmp_path это /tmp/pytest-of-<user>/pytest-<n>/test_handle_show_logs0
        # 1) Создаём папку logs внутри tmp_path
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        # 2) Сюда кладём один лог-файл
        log_file = logs_dir / "bot_2025-06-09.log"
        log_file.write_text("some log content")

        # 3) Подменяем в коде константу BASE_DIR на наш tmp_path
        monkeypatch.setattr(
            "bot.BASE_DIR",
            tmp_path,
        )

        # 4) Мокаем отправку документов, как раньше
        sent_docs = []

        async def fake_answer_document(self, document, **kwargs):
            sent_docs.append(document)

        monkeypatch.setattr(
            "bot.handle_show_logs.__globals__['FSInputFile']",
            lambda path: path,  # если нужно просто вернуть путь
        )
        monkeypatch.setattr(
            "bot.CallbackQuery.message.answer_document",
            fake_answer_document,
        )

        # 5) Запускаем хэндлер через dp._process_update
        await bot.dp._process_update(
            bot=bot.bot,
            update=Update(
                update_id=1,
                callback_query=callback_query,
            ),
        )

        # 6) Проверяем, что отправилось именно наш файл
        assert sent_docs == [str(log_file)]
