import pytest
from bot import Bot  # Импортируйте ваш класс


@pytest.fixture
def bot():
    """Фикстура для инициализации бота."""
    return Bot(max_usdt_to_spend=100)


def test_adjust_qty(bot):
    """Проверяет корректировку количества."""
    assert (
        bot.adjust_qty(0.0001) == 0.001
    )  # Пример значения, которое корректируется до минимального допустимого
    assert (
        bot.adjust_qty(1.23456) == 1.234
    )  # Пример округления количества до нужного знака


def test_generate_signal(bot):
    """Проверяет генерацию торгового сигнала."""
    # Создаем пример данных
    import pandas as pd

    data = pd.DataFrame(
        {
            "close": [100, 105, 102, 108, 107],
            "high": [101, 106, 103, 109, 108],
            "low": [99, 104, 101, 107, 106],
        }
    )

    signal = bot.generate_signal(data)
    assert signal in [0, 1]  # Проверяем, что сигнал является валидным (0 или 1)


def test_execute_trade(bot):
    """Проверяет выполнение торговой операции."""
    signal = 1  # Покупка
    qty = 0.001
    bot.execute_trade(signal, qty)
    # Предположим, что метод `place_order` возвращает некоторый объект
    # Добавьте проверки, если есть ожидаемые значения для результатов
