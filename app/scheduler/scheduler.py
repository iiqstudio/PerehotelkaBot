import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.config import Settings
from app.services.notifications import dispatch_due_notifications
from app.services.time import local_now

logger = logging.getLogger(__name__)


def create_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.zoneinfo)

    async def tick() -> None:
        async with session_factory() as session:
            await dispatch_due_notifications(session, bot, local_now(settings))

    scheduler.add_job(tick, "interval", minutes=1, id="notification_tick", max_instances=1, coalesce=True)
    return scheduler
