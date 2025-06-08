from core.config import settings


def check_for_admin(tg_id: int) -> bool:
    if tg_id == int(settings.bot.admin):
        return True
    return False
