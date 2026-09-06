from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.statistics import stats_for_user
from app.services.text import money

router = Router()


@router.message(F.text == "📊 Статистика")
async def statistics(message: Message, session: AsyncSession) -> None:
    stats = await stats_for_user(session, message.from_user.id)
    await message.answer(
        "📊 Статистика\n"
        f"Всего желаний: {stats['total']}\n"
        f"Активных: {stats['active']}\n"
        f"Отменённых: {stats['cancelled']}\n"
        f"Купленных: {stats['purchased']}\n"
        f"Отказов: {stats['cancelled_percent']}%\n"
        f"Потенциально сохранено: {money(stats['saved'])}\n"
        f"Фактические покупки: {money(stats['spent'])}\n"
        f"Полезных после недели: {stats['useful']}\n"
        f"Лишних после недели: {stats['useless']}"
    )
