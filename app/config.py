from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import os


@dataclass(frozen=True)
class Settings:
    bot_token: str
    allowed_user_ids: set[int]
    timezone: str
    database_path: str

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings() -> Settings:
    load_dotenv()
    token = (
        os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("TOKEN")
        or ""
    )
    raw_ids = os.getenv("ALLOWED_USER_IDS", "")
    timezone = os.getenv("TIMEZONE", "Europe/Moscow")
    database_path = os.getenv("DATABASE_PATH", "data/bot.db")
    allowed_user_ids = {int(part.strip()) for part in raw_ids.split(",") if part.strip()}
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        bot_token=token,
        allowed_user_ids=allowed_user_ids,
        timezone=timezone,
        database_path=database_path,
    )
