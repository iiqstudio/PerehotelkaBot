from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import inline
from app.database.models import User

router = Router()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message, session: AsyncSession) -> None:
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    enabled = "включены" if user and user.notifications_enabled else "выключены"
    await message.answer(
        f"Уведомления: {enabled}\nТихие часы: 22:00-09:00\nЧасовой пояс: {user.timezone if user else 'Europe/Moscow'}",
        reply_markup=inline(
            [
                [("Включить уведомления", "settings:notify:on"), ("Выключить", "settings:notify:off")],
                [("Удалить историю", "settings:delete:confirm")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("settings:notify:"))
async def notify_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    if user:
        user.notifications_enabled = callback.data.endswith(":on")
    await callback.message.answer("Настройки уведомлений сохранены.")
    await callback.answer()


@router.callback_query(F.data == "settings:delete:confirm")
async def delete_confirm(callback: CallbackQuery) -> None:
    await callback.message.answer("Удаление истории подготовлено технически, но в MVP не включено.")
    await callback.answer()
