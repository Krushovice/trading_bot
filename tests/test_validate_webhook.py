from pydantic import ValidationError
import pytest

from trading_bot.schemas import TradingViewSignal


class TestValidateWebhook:
    def test_valid_webhook(self, valid_webhook_data):
        assert TradingViewSignal.model_validate(valid_webhook_data)

    def test_invalid_webhook(self, invalid_values_webhook_data):
        with pytest.raises(ValidationError) as exc_info:
            TradingViewSignal.model_validate(invalid_values_webhook_data)

        # Дополнительно можно проверить, что хотя бы одно поле именно "side" или "qty" или "price"
        errors = exc_info.value.errors()
        # Собираем названия полей, которые pydantic посчитал некорректными:
        failed_fields = {e["loc"][0] for e in errors}

        # Например, хотя бы одно из этих полей точно должно присутствовать в сетах ошибок:
        assert (
            "side" in failed_fields
            or "qty" in failed_fields
            or "price" in failed_fields
            or "max_lag" in failed_fields
        )

    def test_unexpected_webhook(self, unexpected_webhook_data):
        with pytest.raises(ValidationError):
            TradingViewSignal.model_validate(unexpected_webhook_data)
