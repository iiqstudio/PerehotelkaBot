from datetime import datetime

from app.config import Settings


def local_now(settings: Settings) -> datetime:
    return datetime.now(settings.zoneinfo).replace(tzinfo=None)
