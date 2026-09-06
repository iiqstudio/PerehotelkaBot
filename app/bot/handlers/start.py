from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import main_menu
from app.config import Settings
from app.services.wish_service import get_or_create_user

router = Router()


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession, settings: Settings) -> None:
    await get_or_create_user(session, message.from_user, settings.timezone)
    await message.answer("Карантин покупок включён.", reply_markup=main_menu())


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Текущее заполнение отменено.", reply_markup=main_menu())
