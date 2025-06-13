from datetime import datetime

from fastapi import HTTPException
import httpx

from core.config import settings
from trade_service.schemas import TradingViewSignal


BOT_API_URL = f"{settings.trade_config.host_url}{settings.api_prefix.bot_alert_path}"


async def validate_secret(signal: TradingViewSignal) -> None:
    if signal.secret != settings.trade_config.secret:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid secret",
        )


class AlertThrottler:
    def __init__(self):
        self.last_alert_time: datetime | None = None
        self.throttle_seconds = 5

    async def send(self, error_html: str):
        now = datetime.now()

        if (
            self.last_alert_time
            and (now - self.last_alert_time).total_seconds() < self.throttle_seconds
        ):
            return  # подавляем частые повторы

        self.last_alert_time = now

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    BOT_API_URL,
                    json={
                        "error": error_html,
                        "key": settings.bot.token,
                    },
                    timeout=5.0,
                )
        except Exception as e:
            print(f"[ALERT ERROR] Failed to notify Telegram: {e}")


# Экземпляр — можно использовать как singleton
alert_throttler = AlertThrottler()


async def alert_telegram_admins(error_html: str):
    await alert_throttler.send(error_html)
