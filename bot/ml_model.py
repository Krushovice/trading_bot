import os
import joblib
import ta
import numpy as np
import pandas as pd
import traceback
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from typing import Tuple

from .logger import setup_logger

# Инициализация логгера
logger = setup_logger(__name__)


class TradingModel:
    def __init__(
        self,
        model_path: str = "trading_model.pkl",
        n_estimators: int = 100,
        use_class_weights: bool = True,
    ):
        """
        Инициализация модели и ее параметров.
        :param model_path: Путь для сохранения/загрузки модели.
        :param n_estimators: Количество деревьев в случайном лесу.
        :param use_class_weights: Использовать ли веса классов для несбалансированных данных.
        """
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = os.getenv("MODEL_PATH", model_path)
        self.n_estimators = n_estimators
        self.use_class_weights = use_class_weights

    def validate_data(self, df: pd.DataFrame) -> None:
        """
        Проверяет наличие необходимых столбцов и корректность типов данных в DataFrame.
        :param df: DataFrame с историческими данными
        """
        required_columns = {"close"}
        if not required_columns.issubset(df.columns):
            raise ValueError(f"DataFrame должен содержать столбцы: {required_columns}")

        if not pd.api.types.is_numeric_dtype(df["close"]):
            raise TypeError("Столбец 'close' должен быть числовым типом.")

    def prepare_data(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Подготовка данных для обучения модели.
        :param df: DataFrame с историческими данными
        :return: Разделенные на тренировочные и тестовые данные (X_train, X_test, y_train, y_test)
        """
        self.validate_data(df)

        # Пример: Используем цены закрытия и MACD в качестве признаков
        df["macd"], df["macd_signal"], df["macd_diff"] = self.calculate_macd(
            df["close"]
        )
        df["price_diff"] = df["close"].diff()  # разница в цене закрытия

        # Удаляем строки с NaN значениями
        df.dropna(inplace=True)

        # Формируем признаки и целевые метки
        X = df[["close", "macd", "macd_signal", "macd_diff", "price_diff"]].values
        y = np.where(df["price_diff"] > 0, 1, 0)  # 1 - Buy, 0 - Sell

        # Масштабируем данные
        X = self.scaler.fit_transform(X)

        # Разделение на тренировочную и тестовую выборки
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        return X_train, X_test, y_train, y_test

    def calculate_macd(
        self, close: pd.Series
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Рассчитывает MACD на основе цены закрытия.
        :param close: pd.Series с ценами закрытия
        :return: MACD линии и сигнал
        """
        macd = ta.trend.MACD(close)
        macd_line = macd.macd()
        macd_signal_line = macd.macd_signal()
        macd_diff = macd_line - macd_signal_line
        return macd_line, macd_signal_line, macd_diff

    def train(self, df: pd.DataFrame) -> None:
        """
        Обучение модели на исторических данных.
        :param df: DataFrame с историческими данными
        """
        X_train, X_test, y_train, y_test = self.prepare_data(df)

        # Инициализация и обучение модели с учетом веса классов, если необходимо
        class_weight = "balanced" if self.use_class_weights else None
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators, random_state=42, class_weight=class_weight
        )
        self.model.fit(X_train, y_train)

        # Оценка точности модели
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"Model Accuracy: {accuracy:.2f}")

        # Сохранение модели на диск
        self.save_model()

    def load_model(self) -> None:
        """
        Загрузка модели с диска.
        """
        if os.path.exists(self.model_path):
            self.model, self.scaler = joblib.load(self.model_path)
            logger.info("Model loaded successfully.")
        else:
            raise FileNotFoundError(
                "Model file not found. Please train the model first."
            )

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Прогноз на основе входных данных.
        :param X: np.array с данными для предсказания
        :return: Прогноз (1 - Buy, 0 - Sell)
        """
        if self.model is None:
            raise ValueError(
                "Model is not loaded or trained. Please train or load the model first."
            )
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def save_model(self) -> None:
        """
        Сохраняет модель в файл.
        """
        try:
            joblib.dump((self.model, self.scaler), self.model_path)
            logger.info(f"Model saved successfully to {self.model_path}.")
        except Exception as e:
            logger.error(f"Exception occurred while saving model: {e}")
            logger.error(traceback.format_exc())
            raise
