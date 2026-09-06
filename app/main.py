import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import build_router
from app.bot.middlewares.access import AccessMiddleware
from app.bot.middlewares.db import DbSessionMiddleware
from app.config import load_settings
from app.database.session import init_db, make_session_factory
from app.scheduler.scheduler import create_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty")
    if not settings.allowed_user_ids:
        raise RuntimeError("ALLOWED_USER_IDS is empty")

    session_factory = make_session_factory(settings.db_url)
    await init_db(session_factory)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage(), settings=settings)
    dp.update.middleware(AccessMiddleware(settings.allowed_user_ids))
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.include_router(build_router())

    scheduler = create_scheduler(session_factory, bot, settings)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await session_factory.kw["bind"].dispose()


if __name__ == "__main__":
    asyncio.run(main())
