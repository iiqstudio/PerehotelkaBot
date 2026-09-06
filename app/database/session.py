from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base


def make_engine(db_url: str):
    engine = create_async_engine(db_url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def make_session_factory(db_url: str) -> async_sessionmaker[AsyncSession]:
    engine = make_engine(db_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
