from datetime import datetime
import os

from fastapi import HTTPException
import httpx

from trading_bot.schemas import TradingViewSignal


SECRET_KEY = os.getenv("MY_SECRET_KEY")
BOT_API_URL = "http://127.0.0.1:8000/alert-critical"
BOT_SECRET_KEY = os.getenv("BOT_TOKEN")


async def validate_secret(signal: TradingViewSignal) -> None:
    if signal.secret != SECRET_KEY:
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
                        "key": BOT_SECRET_KEY,
                    },
                    timeout=5.0,
                )
        except Exception as e:
            print(f"[ALERT ERROR] Failed to notify Telegram: {e}")


# Экземпляр — можно использовать как singleton
alert_throttler = AlertThrottler()


async def alert_telegram_admins(error_html: str):
    await alert_throttler.send(error_html)
