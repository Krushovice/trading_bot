import os


ADMIN_ID = int(os.getenv("ADMIN_ID"))


def check_for_admin(tg_id: int) -> bool:
    if tg_id == ADMIN_ID:
        return True
    return False
