import pytest
from aiogram import Bot
from aiogram.types import Update, Message, Chat, User, CallbackQuery

from trade_service import Bybit
from core.config import settings

admin_id = settings.bot.admin


class DummyClient:
    def get_instruments_info(self, symbol, category):
        # Если не будет замены через monkeypatch, тест упадёт
        # мы хотим гарантированно подменять этот метод
        raise RuntimeError("unmocked!")

    def get_tickers(self, category, symbol):
        raise RuntimeError("unmocked!")


@pytest.fixture()
def bybit(monkeypatch):
    b = Bybit(use_testnet=True)

    b.client = DummyClient()
    return b


# Чтобы pytest-asyncio подхватил async-фикстуры
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def admin_user() -> User:
    return User(
        id=admin_id,
        is_bot=False,
        first_name="TestAdmin",
        username="adminuser",
    )


@pytest.fixture
def admin_chat(admin_user) -> Chat:
    return Chat(
        id=admin_user.id,
        type="private",
        username=admin_user.username,
        first_name=admin_user.first_name,
    )


@pytest.fixture
def message(admin_user, admin_chat) -> Message:
    # Простейшее сообщение с текстом /start
    return Message(
        message_id=1,
        date=0,
        text="/start",
        from_user=admin_user,
        chat=admin_chat,
    )


@pytest.fixture
def update(message) -> Update:
    # Оборачиваем Message в Update
    return Update(update_id=1, message=message)


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    """
    Глобально подменяем Bot.__call__ на фейковый метод,
    чтобы ни один тест не улетал в реальный Telegram API.
    """

    async def fake_call(
        self,
        method,
        *args,
        **kwargs,
    ):
        # ничего не шлём, просто возвращаем TelegramMethod
        return method

    monkeypatch.setattr(
        Bot,
        "__call__",
        fake_call,
    )


@pytest.fixture
def callback_query(message, admin_user) -> CallbackQuery:
    # Сообщение, на котором вызван каллбек
    return CallbackQuery(
        id="1",
        from_user=admin_user,
        chat_instance=str(admin_user.id),
        data="show_logs",
        message=message,
    )


# @pytest.fixture(autouse=True)
# def override_dependencies(monkeypatch, tmp_path):
#     monkeypatch.setenv("BASE_DIR", str(tmp_path))  # базовая папка
#     # или если используете Depends, то в TestClient передать app.dependency_overrides
#     app.dependency_overrides[load_logs_dir] = lambda: tmp_path / "logs"
#     app.dependency_overrides[file_factory] = lambda p: p
