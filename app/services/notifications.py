from datetime import datetime, timedelta, time
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot.keyboards.common import inline
from app.database.models import User, Wish, WishStatus
from app.services.text import h, money
from app.services.wish_service import mark_ready, notification_exists, record_notification

logger = logging.getLogger(__name__)

FIRST_REVIEW = "first_review"
FIRST_REVIEW_REMINDER = "first_review_reminder"
QUARANTINE_DONE = "quarantine_done"
FINAL_PAUSE_DONE = "final_pause_done"
POST_PURCHASE_REVIEW = "post_purchase_review"


def in_quiet_hours(now: datetime, start: time, end: time) -> bool:
    current = now.timetz().replace(tzinfo=None)
    if start < end:
        return start <= current < end
    return current >= start or current < end


async def dispatch_due_notifications(session: AsyncSession, bot: Bot, now: datetime) -> None:
    result = await session.execute(
        select(Wish)
        .options(selectinload(Wish.user))
        .where(Wish.next_action_at.is_not(None), Wish.next_action_at <= now)
        .order_by(Wish.next_action_at.asc())
        .limit(50)
    )
    for wish in result.scalars().all():
        try:
            await dispatch_wish(session, bot, wish, now)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to dispatch notification for wish %s", wish.id)


async def dispatch_wish(session: AsyncSession, bot: Bot, wish: Wish, now: datetime) -> None:
    user = wish.user
    if not user.notifications_enabled:
        return
    if in_quiet_hours(now, user.quiet_hours_start, user.quiet_hours_end):
        wish.next_action_at = datetime.combine(now.date(), user.quiet_hours_end)
        if wish.next_action_at <= now:
            wish.next_action_at += timedelta(days=1)
        return

    if wish.status == WishStatus.WAITING_FIRST_REVIEW.value:
        if not await notification_exists(session, wish.id, FIRST_REVIEW):
            sent = await send(
                bot,
                user.telegram_id,
                f"Прошли сутки. Ты всё ещё хочешь купить «{h(wish.title)}» примерно за {h(money(wish.estimated_price))}?",
                inline(
                    [
                        [("Уже не хочу", f"review:no:{wish.id}")],
                        [("Пока не уверен", f"review:unsure:{wish.id}")],
                        [("Да, желание осталось", f"review:yes:{wish.id}")],
                    ]
                ),
            )
            if sent:
                await record_notification(session, wish.id, FIRST_REVIEW, now)
                wish.next_action_at = now + timedelta(hours=24)
        elif not wish.reminder_sent_at and not await notification_exists(session, wish.id, FIRST_REVIEW_REMINDER):
            sent = await send(
                bot,
                user.telegram_id,
                f"Напоминаю про «{h(wish.title)}». Ответь на первую проверку, когда будет удобно.",
            )
            if sent:
                wish.reminder_sent_at = now
                await record_notification(session, wish.id, FIRST_REVIEW_REMINDER, now)
                wish.next_action_at = wish.quarantine_until
        else:
            wish.next_action_at = wish.quarantine_until
        return

    if wish.status == WishStatus.WAITING_QUARANTINE.value and wish.quarantine_until <= now:
        if not await notification_exists(session, wish.id, QUARANTINE_DONE):
            await mark_ready(wish, now)
            sent = await send(
                bot,
                user.telegram_id,
                f"«{h(wish.title)}» находятся в списке уже достаточно долго. Желание пережило карантин. Теперь можно принять решение осознанно.",
                inline(
                    [
                        [("Начать выбор", f"decision:start:{wish.id}")],
                        [("Подождать ещё", f"wait:menu:{wish.id}"), ("Отказаться", f"decision:cancel:{wish.id}")],
                    ]
                ),
            )
            if sent:
                await record_notification(session, wish.id, QUARANTINE_DONE, now)
        return

    if wish.status == WishStatus.FINAL_PAUSE.value:
        if not await notification_exists(session, wish.id, FINAL_PAUSE_DONE):
            wish.status = WishStatus.RESEARCHING.value
            wish.next_action_at = None
            sent = await send(
                bot,
                user.telegram_id,
                f"Финальная пауза по «{h(wish.title)}» закончилась. Можно принять решение.",
                inline([[("Купить выбранное", f"buy:menu:{wish.id}")], [("Отказаться", f"wish:cancel:{wish.id}")]]),
            )
            if sent:
                await record_notification(session, wish.id, FINAL_PAUSE_DONE, now)
        return

    if wish.status == WishStatus.PURCHASED.value and wish.purchased_at and wish.purchased_at + timedelta(days=7) <= now:
        if not await notification_exists(session, wish.id, POST_PURCHASE_REVIEW):
            sent = await send(
                bot,
                user.telegram_id,
                f"Прошла неделя после покупки «{h(wish.title)}». Покупка оказалась полезной?",
                inline(
                    [
                        [("Да, очень", f"rating:yes_very:{wish.id}"), ("Скорее да", f"rating:rather_yes:{wish.id}")],
                        [("Скорее нет", f"rating:rather_no:{wish.id}"), ("Нет, была лишней", f"rating:no:{wish.id}")],
                    ]
                ),
            )
            if sent:
                await record_notification(session, wish.id, POST_PURCHASE_REVIEW, now)


async def send(bot: Bot, chat_id: int, text: str, reply_markup=None) -> bool:
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
        return True
    except TelegramAPIError:
        logger.exception("Telegram send failed for chat %s", chat_id)
        return False
