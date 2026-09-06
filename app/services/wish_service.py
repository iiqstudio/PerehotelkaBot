from datetime import datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Notification, ProductOption, User, Wish, WishStatus
from app.services.quarantine import first_review_time, quarantine_until


ACTIVE_STATUSES = {
    WishStatus.WAITING_FIRST_REVIEW,
    WishStatus.WAITING_QUARANTINE,
    WishStatus.READY_FOR_DECISION,
    WishStatus.RESEARCHING,
    WishStatus.FINAL_PAUSE,
    WishStatus.DECIDED_TO_BUY,
}


async def get_or_create_user(session: AsyncSession, telegram_user, timezone: str) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_user.id))
    user = result.scalar_one_or_none()
    if user:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        return user
    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        timezone=timezone,
        created_at=datetime.now(),
    )
    session.add(user)
    await session.flush()
    return user


async def create_wish(
    session: AsyncSession,
    user: User,
    title: str,
    estimated_price: int | None,
    purchase_type: str,
    reason: str | None,
    current_alternative: str | None,
    now: datetime,
) -> Wish:
    first_review_at = first_review_time(now)
    until = quarantine_until(now, estimated_price)
    wish = Wish(
        user_id=user.id,
        title=title,
        estimated_price=estimated_price,
        purchase_type=purchase_type,
        reason=reason,
        current_alternative=current_alternative,
        status=WishStatus.WAITING_FIRST_REVIEW.value,
        created_at=now,
        first_review_at=first_review_at,
        quarantine_until=until,
        next_action_at=first_review_at,
    )
    session.add(wish)
    await session.flush()
    return wish


def wish_query() -> Select[tuple[Wish]]:
    return select(Wish).options(selectinload(Wish.options), selectinload(Wish.user))


async def get_user_wish(session: AsyncSession, telegram_id: int, wish_id: int) -> Wish | None:
    result = await session.execute(
        wish_query().join(User).where(User.telegram_id == telegram_id, Wish.id == wish_id)
    )
    return result.scalar_one_or_none()


async def list_wishes(session: AsyncSession, telegram_id: int, statuses: set[WishStatus]) -> list[Wish]:
    result = await session.execute(
        wish_query()
        .join(User)
        .where(User.telegram_id == telegram_id, Wish.status.in_([s.value for s in statuses]))
        .order_by(Wish.next_action_at.asc().nullslast(), Wish.created_at.desc())
    )
    return list(result.scalars().all())


async def cancel_wish(session: AsyncSession, wish: Wish, now: datetime) -> None:
    wish.status = WishStatus.CANCELLED.value
    wish.cancelled_at = now
    wish.next_action_at = None


async def answer_first_review(session: AsyncSession, wish: Wish, answer: str, now: datetime) -> None:
    wish.first_review_answered_at = now
    if answer == "no":
        await cancel_wish(session, wish, now)
        return
    if wish.quarantine_until <= now:
        wish.status = WishStatus.READY_FOR_DECISION.value
        wish.next_action_at = now
    else:
        wish.status = WishStatus.WAITING_QUARANTINE.value
        wish.next_action_at = wish.quarantine_until


async def save_consequence(session: AsyncSession, wish: Wish, consequence: str, now: datetime) -> None:
    wish.no_purchase_consequence = consequence
    await answer_first_review(session, wish, "yes", now)


async def mark_ready(wish: Wish, now: datetime) -> None:
    wish.status = WishStatus.READY_FOR_DECISION.value
    wish.next_action_at = now


async def extend_wait(wish: Wish, days: int, now: datetime) -> None:
    wish.status = WishStatus.WAITING_QUARANTINE.value
    wish.quarantine_until = now + timedelta(days=days)
    wish.next_action_at = wish.quarantine_until


async def start_research(wish: Wish, criteria: str) -> None:
    wish.criteria = criteria
    wish.status = WishStatus.RESEARCHING.value
    wish.next_action_at = None


async def add_option(
    session: AsyncSession,
    wish: Wish,
    name: str,
    price: int | None,
    url: str | None,
    comment: str | None,
    now: datetime,
) -> ProductOption:
    option = ProductOption(
        wish_id=wish.id,
        name=name,
        price=price,
        url=url,
        comment=comment,
        created_at=now,
    )
    session.add(option)
    await session.flush()
    return option


async def start_final_pause(wish: Wish, now: datetime) -> None:
    wish.status = WishStatus.FINAL_PAUSE.value
    wish.next_action_at = now + timedelta(hours=24)


async def decide_to_buy(wish: Wish, selected_option_id: int | None = None) -> None:
    wish.status = WishStatus.DECIDED_TO_BUY.value
    wish.next_action_at = None
    for option in wish.options:
        option.is_selected = option.id == selected_option_id


async def mark_purchased(wish: Wish, final_price: int | None, now: datetime, selected_option_id: int | None = None) -> None:
    await decide_to_buy(wish, selected_option_id)
    wish.status = WishStatus.PURCHASED.value
    wish.final_price = final_price
    wish.purchased_at = now
    wish.next_action_at = now + timedelta(days=7)


async def save_purchase_rating(wish: Wish, rating: str, comment: str | None = None) -> None:
    wish.post_purchase_rating = rating
    wish.post_purchase_comment = comment
    wish.next_action_at = None


async def update_price_without_shortening_quarantine(wish: Wish, price: int | None) -> None:
    old_until = wish.quarantine_until
    wish.estimated_price = price
    new_until = quarantine_until(wish.created_at, price)
    if new_until > old_until:
        wish.quarantine_until = new_until
        if wish.status == WishStatus.WAITING_QUARANTINE.value:
            wish.next_action_at = new_until


async def notification_exists(session: AsyncSession, wish_id: int, event_type: str) -> bool:
    result = await session.execute(
        select(Notification.id).where(Notification.wish_id == wish_id, Notification.event_type == event_type)
    )
    return result.scalar_one_or_none() is not None


async def record_notification(session: AsyncSession, wish_id: int, event_type: str, now: datetime) -> None:
    session.add(Notification(wish_id=wish_id, event_type=event_type, sent_at=now))


async def stats_for_user(session: AsyncSession, telegram_id: int) -> dict[str, int | float]:
    result = await session.execute(select(User.id).where(User.telegram_id == telegram_id))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        return empty_stats()

    total = await session.scalar(select(func.count(Wish.id)).where(Wish.user_id == user_id)) or 0
    active = await session.scalar(
        select(func.count(Wish.id)).where(Wish.user_id == user_id, Wish.status.in_([s.value for s in ACTIVE_STATUSES]))
    ) or 0
    cancelled = await session.scalar(
        select(func.count(Wish.id)).where(Wish.user_id == user_id, Wish.status == WishStatus.CANCELLED.value)
    ) or 0
    purchased = await session.scalar(
        select(func.count(Wish.id)).where(Wish.user_id == user_id, Wish.status == WishStatus.PURCHASED.value)
    ) or 0
    saved = await session.scalar(
        select(func.coalesce(func.sum(Wish.estimated_price), 0)).where(
            Wish.user_id == user_id, Wish.status == WishStatus.CANCELLED.value
        )
    ) or 0
    spent = await session.scalar(
        select(func.coalesce(func.sum(Wish.final_price), 0)).where(
            Wish.user_id == user_id, Wish.status == WishStatus.PURCHASED.value
        )
    ) or 0
    useful = await session.scalar(
        select(func.count(Wish.id)).where(
            Wish.user_id == user_id,
            Wish.status == WishStatus.PURCHASED.value,
            Wish.post_purchase_rating.in_(["yes_very", "rather_yes"]),
        )
    ) or 0
    useless = await session.scalar(
        select(func.count(Wish.id)).where(
            Wish.user_id == user_id,
            Wish.status == WishStatus.PURCHASED.value,
            Wish.post_purchase_rating.in_(["rather_no", "no"]),
        )
    ) or 0
    return {
        "total": total,
        "active": active,
        "cancelled": cancelled,
        "purchased": purchased,
        "cancelled_percent": round(cancelled * 100 / total) if total else 0,
        "saved": int(saved),
        "spent": int(spent),
        "useful": useful,
        "useless": useless,
    }


def empty_stats() -> dict[str, int | float]:
    return {
        "total": 0,
        "active": 0,
        "cancelled": 0,
        "purchased": 0,
        "cancelled_percent": 0,
        "saved": 0,
        "spent": 0,
        "useful": 0,
        "useless": 0,
    }
