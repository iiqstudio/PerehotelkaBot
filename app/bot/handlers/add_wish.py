from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import inline, main_menu
from app.bot.states.add_wish import AddWish
from app.config import Settings
from app.services.text import clean_text, h, money, parse_price
from app.services.time import local_now
from app.services.wish_service import create_wish, get_or_create_user

router = Router()


@router.message(F.text == "➕ Записать желание")
async def add_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddWish.title)
    await message.answer("Что тебе захотелось купить?\n\nПример: Умные часы.")


@router.message(AddWish.title)
async def add_title(message: Message, state: FSMContext) -> None:
    title = clean_text(message.text or "", 200)
    if not title:
        await message.answer("Напиши название покупки.")
        return
    await state.update_data(title=title)
    await state.set_state(AddWish.price)
    await message.answer(
        "Сколько это примерно стоит? Напиши сумму в рублях.",
        reply_markup=inline([[("Не знаю цену", "add:price_unknown")]]),
    )


@router.callback_query(AddWish.price, F.data == "add:price_unknown")
async def add_unknown_price(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(estimated_price=None)
    await state.set_state(AddWish.purchase_type)
    await callback.message.answer("Выбери тип покупки:", reply_markup=purchase_type_keyboard())
    await callback.answer()


@router.message(AddWish.price)
async def add_price(message: Message, state: FSMContext) -> None:
    price = parse_price(message.text or "")
    if price is None:
        await message.answer("Цена должна быть больше нуля. Можно написать, например: 15 000 ₽.")
        return
    await state.update_data(estimated_price=price)
    await state.set_state(AddWish.purchase_type)
    await message.answer("Выбери тип покупки:", reply_markup=purchase_type_keyboard())


def purchase_type_keyboard():
    return inline(
        [
            [("Необходимость", "add:type:Необходимость")],
            [("Улучшение", "add:type:Улучшение")],
            [("Просто хочется", "add:type:Просто хочется")],
        ]
    )


@router.callback_query(AddWish.purchase_type, F.data.startswith("add:type:"))
async def add_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(purchase_type=callback.data.removeprefix("add:type:"))
    await state.set_state(AddWish.reason)
    await callback.message.answer(
        "Какую проблему решит эта покупка или почему она тебе нужна?",
        reply_markup=inline([[("Пропустить", "add:skip_reason")]]),
    )
    await callback.answer()


@router.callback_query(AddWish.reason, F.data == "add:skip_reason")
async def skip_reason(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(reason=None)
    await ask_current(callback.message, state)
    await callback.answer()


@router.message(AddWish.reason)
async def add_reason(message: Message, state: FSMContext) -> None:
    await state.update_data(reason=clean_text(message.text or ""))
    await ask_current(message, state)


async def ask_current(message: Message, state: FSMContext) -> None:
    await state.set_state(AddWish.current_alternative)
    await message.answer(
        "У тебя уже есть вещь, которая выполняет эту задачу?",
        reply_markup=inline(
            [
                [("Да, и она работает", "add:current:Да, и она работает")],
                [("Да, но есть проблема", "add:current:Да, но есть проблема")],
                [("Нет", "add:current:Нет"), ("Не применимо", "add:current:Не применимо")],
            ]
        ),
    )


@router.callback_query(AddWish.current_alternative, F.data.startswith("add:current:"))
async def add_current(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(current_alternative=callback.data.removeprefix("add:current:"))
    await state.set_state(AddWish.confirm)
    await callback.message.answer(card(await state.get_data()), reply_markup=confirm_keyboard())
    await callback.answer()


def card(data: dict) -> str:
    return (
        f"<b>{h(data['title'])}</b>\n"
        f"Цена: около {h(money(data.get('estimated_price')))}\n"
        f"Тип: {h(data['purchase_type'].lower())}\n"
        f"Причина: {h(data.get('reason') or 'не указана')}\n"
        f"Сейчас: {h(data.get('current_alternative') or 'не указано')}"
    )


def confirm_keyboard():
    return inline(
        [
            [("Отправить в карантин", "add:save")],
            [("Изменить", "add:restart"), ("Отмена", "add:cancel")],
        ]
    )


@router.callback_query(AddWish.confirm, F.data == "add:restart")
async def restart_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddWish.title)
    await callback.message.answer("Что тебе захотелось купить?")
    await callback.answer()


@router.callback_query(AddWish.confirm, F.data == "add:cancel")
async def cancel_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Запись желания отменена.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(AddWish.confirm, F.data == "add:save")
async def save_add(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    data = await state.get_data()
    user = await get_or_create_user(session, callback.from_user, settings.timezone)
    now = local_now(settings)
    await create_wish(
        session=session,
        user=user,
        title=data["title"],
        estimated_price=data.get("estimated_price"),
        purchase_type=data["purchase_type"],
        reason=data.get("reason"),
        current_alternative=data.get("current_alternative"),
        now=now,
    )
    await state.clear()
    await callback.message.answer(
        "Желание записано. Сейчас ничего искать не нужно. Я вернусь к нему через 24 часа.",
        reply_markup=main_menu(),
    )
    await callback.answer()
