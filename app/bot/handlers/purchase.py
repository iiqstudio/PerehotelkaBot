from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import inline
from app.bot.states.add_wish import OptionForm, PurchaseForm
from app.config import Settings
from app.services.text import clean_text, h, money, parse_price
from app.services.time import local_now
from app.services.wish_service import add_option, get_user_wish, mark_purchased, save_purchase_rating, start_final_pause

router = Router()


@router.callback_query(F.data.startswith("option:add:"))
async def option_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OptionForm.name)
    await state.update_data(wish_id=int(callback.data.rsplit(":", 1)[1]), option_count=0)
    await callback.message.answer("Напиши название выбранного варианта.")
    await callback.answer()


@router.message(OptionForm.name)
async def option_name(message: Message, state: FSMContext) -> None:
    await state.update_data(option_name=clean_text(message.text or "", 200))
    await state.set_state(OptionForm.price)
    await message.answer("Цена варианта? Можно написать «не знаю».")


@router.message(OptionForm.price)
async def option_price(message: Message, state: FSMContext) -> None:
    await state.update_data(option_price=parse_price(message.text or ""))
    await state.set_state(OptionForm.url)
    await message.answer("Ссылка на вариант, если есть. Если нет, напиши «пропустить».")


@router.message(OptionForm.url)
async def option_url(message: Message, state: FSMContext) -> None:
    raw = clean_text(message.text or "")
    await state.update_data(option_url=None if raw.lower() in {"пропустить", "нет", "-"} else raw)
    await state.set_state(OptionForm.comment)
    await message.answer("Короткий комментарий, если нужен. Можно написать «пропустить».")


@router.message(OptionForm.comment)
async def option_comment(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    data = await state.get_data()
    wish = await get_user_wish(session, message.from_user.id, data["wish_id"])
    if not wish:
        await state.clear()
        return
    raw_comment = clean_text(message.text or "")
    await add_option(
        session,
        wish,
        data["option_name"],
        data.get("option_price"),
        data.get("option_url"),
        None if raw_comment.lower() in {"пропустить", "нет", "-"} else raw_comment,
        local_now(settings),
    )
    await session.flush()
    await session.refresh(wish, attribute_names=["options"])
    count = len(wish.options)
    await state.clear()
    await message.answer(options_text(wish), reply_markup=options_keyboard(wish.id, count))


def options_text(wish) -> str:
    lines = [f"<b>{h(wish.title)}</b>", "Выбранные варианты:"]
    for idx, option in enumerate(wish.options, 1):
        line = f"{idx}. {h(option.name)} — {h(money(option.price))}"
        if option.comment:
            line += f"\n   {h(option.comment)}"
        if option.url:
            line += f"\n   {h(option.url)}"
        lines.append(line)
    return "\n".join(lines)


def options_keyboard(wish_id: int, count: int):
    rows = []
    if count < 3:
        rows.append([("Добавить ещё вариант", f"option:add:{wish_id}")])
    rows.extend(
        [
            [("Купить выбранное", f"buy:menu:{wish_id}")],
            [("Подумать ещё 24 часа", f"final_pause:{wish_id}"), ("Отказаться", f"wish:cancel:{wish_id}")],
        ]
    )
    return inline(rows)


@router.callback_query(F.data.startswith("final_pause:"))
async def final_pause(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if wish:
        await start_final_pause(wish, local_now(settings))
        await callback.message.answer("Ок, вернусь через 24 часа.")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:menu:"))
async def buy_menu(callback: CallbackQuery) -> None:
    wish_id = callback.data.rsplit(":", 1)[1]
    await callback.message.answer(
        "Ты уже купил вещь или только принял решение?",
        reply_markup=inline(
            [
                [("Уже купил", f"buy:purchased:{wish_id}")],
                [("Решил купить", f"buy:decided:{wish_id}")],
                [("Пока не купил", f"buy:notyet:{wish_id}")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:purchased:"))
async def buy_purchased(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PurchaseForm.final_price)
    await state.update_data(wish_id=int(callback.data.rsplit(":", 1)[1]))
    await callback.message.answer("За сколько в итоге купили? Напиши сумму в рублях.")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:decided:"))
async def buy_decided(callback: CallbackQuery, session: AsyncSession) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if wish:
        wish.status = "decided_to_buy"
        wish.next_action_at = None
        await callback.message.answer("Решение купить зафиксировано. Когда купишь, отметь это в списке готовых к решению.")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:notyet:"))
async def buy_notyet(callback: CallbackQuery) -> None:
    await callback.message.answer("Хорошо, покупку не фиксирую.")
    await callback.answer()


@router.message(PurchaseForm.final_price)
async def final_price(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    price = parse_price(message.text or "")
    if price is None:
        await message.answer("Напиши сумму больше нуля.")
        return
    data = await state.get_data()
    wish = await get_user_wish(session, message.from_user.id, data["wish_id"])
    if wish:
        await mark_purchased(wish, price, local_now(settings))
        await message.answer("Покупка сохранена. Через 7 дней спрошу, оказалась ли она полезной.")
    await state.clear()


@router.callback_query(F.data.startswith("rating:"))
async def rating(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, rating_value, wish_id = callback.data.split(":")
    wish = await get_user_wish(session, callback.from_user.id, int(wish_id))
    if not wish:
        await callback.answer("Не найдено", show_alert=True)
        return
    await save_purchase_rating(wish, rating_value)
    await state.set_state(PurchaseForm.rating_comment)
    await state.update_data(wish_id=wish.id)
    await callback.message.answer("Комментарий к покупке можно написать одним сообщением или нажать «Пропустить».", reply_markup=inline([[("Пропустить", f"rating_skip:{wish.id}")]]))
    await callback.answer()


@router.callback_query(F.data.startswith("rating_skip:"))
async def rating_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Оценка сохранена.")
    await callback.answer()


@router.message(PurchaseForm.rating_comment)
async def rating_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    wish = await get_user_wish(session, message.from_user.id, data["wish_id"])
    if wish:
        wish.post_purchase_comment = clean_text(message.text or "")
        await message.answer("Комментарий сохранён.")
    await state.clear()
