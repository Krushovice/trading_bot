from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class GunicornConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    timeout: int = 900


class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class BotConfig(BaseModel):
    token: str
    secret: str
    admin: int


class AppPath(BaseModel):
    trade_webhook: str = "/trading_webhook"
    bot_webhook: str = "/webhook"
    bot_alert: str = "/alert-critical"


class TradeConfig(BaseModel):
    host_url: str
    secret_key: str


class BybitApiConfig(BaseModel):
    key: str
    secret: str
    test_key: str
    test_secret: str
    sl_pct: float
    timeout: int = 30


class ApiPrefix(BaseModel):
    bot: str = "/bot"
    app: AppPath = AppPath()

    @property
    def bot_webhook_path(self) -> str:
        return f"{self.bot}{self.app.bot_webhook}"

    @property
    def bot_alert_path(self) -> str:
        return f"{self.bot}{self.app.bot_alert}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="API_CONFIG__",
    )
    run: RunConfig = RunConfig()
    gunicorn: GunicornConfig = GunicornConfig()
    bybit_api: BybitApiConfig
    trade_config: TradeConfig
    api_prefix: ApiPrefix = ApiPrefix()
    bot: BotConfig


settings = Settings()
