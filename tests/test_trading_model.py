import pytest
import numpy as np
from bot.ml_model import TradingModel  # Импортируйте ваш класс


@pytest.fixture
def trading_model():
    """Фикстура для инициализации TradingModel."""
    model = TradingModel(
        model_path="test_model.pkl"
    )  # Используйте временный файл для тестов
    model.model = None  # Имитация незагруженной модели
    model.scaler = None
    return model


def test_load_model(trading_model):
    """Проверяет загрузку модели."""
    with pytest.raises(FileNotFoundError):
        trading_model.load_model()  # Ожидаем исключение, т.к. модель не загружена


def test_predict_without_model(trading_model):
    """Проверяет предсказание без загруженной модели."""
    X = np.array([[1, 2, 3, 4, 5, 6]])  # Пример данных для теста
    with pytest.raises(ValueError, match="Model or scaler is not loaded or trained."):
        trading_model.predict(X)  # Ожидаем исключение


@pytest.mark.parametrize(
    "input_data, expected",
    [
        (np.array([[0.5, 0.1, 0.8, 0.3, 0.4, 0.7]]), 1),
        (np.array([[0.1, 0.4, 0.2, 0.5, 0.1, 0.3]]), 0),
    ],
)
def test_predict_with_model(trading_model, input_data, expected):
    """Проверяет предсказание при корректно загруженной модели."""
    # Загружаем фиктивную модель и масштабировщик для теста
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    trading_model.model = LogisticRegression()
    trading_model.scaler = StandardScaler()

    # Подготовка данных и обучение фиктивной модели
    X_train = np.array([[0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1]])
    y_train = np.array([0, 1])
    trading_model.scaler.fit(X_train)
    X_train_scaled = trading_model.scaler.transform(X_train)
    trading_model.model.fit(X_train_scaled, y_train)

    prediction = trading_model.predict(input_data)
    assert prediction[-1] == expected  # Проверяем последний результат предсказания
