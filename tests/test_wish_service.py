from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.database.session import init_db, make_session_factory
from app.database.models import Wish, WishStatus
from app.services.wish_service import (
    answer_first_review,
    cancel_wish,
    create_wish,
    extend_wait,
    get_or_create_user,
    record_notification,
    notification_exists,
    stats_for_user,
    update_price_without_shortening_quarantine,
)


@pytest.fixture
async def session_factory(tmp_path):
    factory = make_session_factory(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await init_db(factory)
    yield factory
    await factory.kw["bind"].dispose()


async def make_wish(session_factory, price=15000):
    async with session_factory() as session:
        user = await get_or_create_user(
            session,
            SimpleNamespace(id=1, username="u", first_name="User"),
            "Europe/Moscow",
        )
        wish = await create_wish(
            session,
            user,
            "Умные часы",
            price,
            "Просто хочется",
            None,
            "Да, и она работает",
            datetime(2026, 9, 6, 12, 0),
        )
        await session.commit()
        return wish.id


async def test_status_transitions_and_cancel(session_factory) -> None:
    wish_id = await make_wish(session_factory, 500)
    async with session_factory() as session:
        wish = await session.get(Wish, wish_id)
        await answer_first_review(session, wish, "unsure", datetime(2026, 9, 7, 12, 0))
        assert wish.status == WishStatus.READY_FOR_DECISION.value
        await cancel_wish(session, wish, datetime(2026, 9, 7, 12, 1))
        assert wish.status == WishStatus.CANCELLED.value
        assert wish.next_action_at is None


async def test_extend_wait(session_factory) -> None:
    wish_id = await make_wish(session_factory)
    async with session_factory() as session:
        wish = await session.get(Wish, wish_id)
        await extend_wait(wish, 3, datetime(2026, 9, 10, 12, 0))
        assert wish.status == WishStatus.WAITING_QUARANTINE.value
        assert wish.next_action_at == datetime(2026, 9, 13, 12, 0)


async def test_price_update_does_not_shorten_quarantine(session_factory) -> None:
    wish_id = await make_wish(session_factory, 60000)
    async with session_factory() as session:
        wish = await session.get(Wish, wish_id)
        old_until = wish.quarantine_until
        await update_price_without_shortening_quarantine(wish, 1000)
        assert wish.quarantine_until == old_until
        await update_price_without_shortening_quarantine(wish, 70000)
        assert wish.quarantine_until == old_until


async def test_notification_is_unique_by_type(session_factory) -> None:
    wish_id = await make_wish(session_factory)
    async with session_factory() as session:
        await record_notification(session, wish_id, "first_review", datetime(2026, 9, 7, 12, 0))
        await session.commit()
    async with session_factory() as session:
        assert await notification_exists(session, wish_id, "first_review")
        assert not await notification_exists(session, wish_id, "other")


async def test_statistics_are_per_user(session_factory) -> None:
    wish_id = await make_wish(session_factory, 15000)
    async with session_factory() as session:
        wish = await session.get(Wish, wish_id)
        await cancel_wish(session, wish, datetime(2026, 9, 8, 12, 0))
        await session.commit()
    async with session_factory() as session:
        stats = await stats_for_user(session, 1)
        assert stats["total"] == 1
        assert stats["cancelled"] == 1
        assert stats["saved"] == 15000
