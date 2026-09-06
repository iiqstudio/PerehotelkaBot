from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import inline
from app.bot.states.add_wish import EditWish
from app.config import Settings
from app.database.models import Wish, WishStatus
from app.services.quarantine import days_label
from app.services.text import clean_text, h, money, parse_price
from app.services.time import local_now
from app.services.wish_service import cancel_wish, get_user_wish, list_wishes, update_price_without_shortening_quarantine

router = Router()


LISTS = {
    "⏳ На карантине": {WishStatus.WAITING_FIRST_REVIEW, WishStatus.WAITING_QUARANTINE, WishStatus.FINAL_PAUSE},
    "✅ Готовы к решению": {WishStatus.READY_FOR_DECISION, WishStatus.RESEARCHING, WishStatus.DECIDED_TO_BUY},
    "📦 Купленные": {WishStatus.PURCHASED},
    "❌ Отменённые": {WishStatus.CANCELLED},
}


@router.message(F.text.in_(LISTS.keys()))
async def show_list(message: Message, session: AsyncSession, settings: Settings) -> None:
    wishes = await list_wishes(session, message.from_user.id, LISTS[message.text])
    if not wishes:
        await message.answer("Здесь пока пусто.")
        return
    for wish in wishes[:10]:
        await message.answer(wish_card(wish, settings), reply_markup=wish_keyboard(wish))


def wish_card(wish: Wish, settings: Settings) -> str:
    now = local_now(settings)
    left = days_label((wish.next_action_at or wish.quarantine_until) - now)
    created = wish.created_at.strftime("%d.%m.%Y")
    return (
        f"<b>{h(wish.title)}</b>\n"
        f"≈ {h(money(wish.estimated_price))}\n"
        f"Тип: {h(wish.purchase_type.lower())}\n"
        f"Статус: {h(wish.status)}\n"
        f"Создано: {created}\n"
        f"До решения: {left}"
    )


def wish_keyboard(wish: Wish):
    rows = [[("Подробнее", f"wish:detail:{wish.id}")]]
    if wish.status != WishStatus.CANCELLED.value and wish.status != WishStatus.PURCHASED.value:
        rows.append([("Отказаться", f"wish:cancel:{wish.id}"), ("Изменить", f"edit:menu:{wish.id}")])
        rows.append([("Продлить ожидание", f"wait:menu:{wish.id}")])
        if wish.status in {WishStatus.RESEARCHING.value, WishStatus.DECIDED_TO_BUY.value}:
            rows.append([("Отметить покупку", f"buy:purchased:{wish.id}")])
    return inline(rows)


@router.callback_query(F.data.startswith("wish:detail:"))
async def detail(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if not wish:
        await callback.answer("Не найдено", show_alert=True)
        return
    text = wish_card(wish, settings)
    if wish.reason:
        text += f"\nПричина: {h(wish.reason)}"
    if wish.current_alternative:
        text += f"\nСейчас: {h(wish.current_alternative)}"
    if wish.criteria:
        text += f"\nКритерии: {h(wish.criteria)}"
    await callback.message.answer(text, reply_markup=wish_keyboard(wish))
    await callback.answer()


@router.callback_query(F.data.startswith("wish:cancel:"))
async def cancel(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if not wish:
        await callback.answer("Не найдено", show_alert=True)
        return
    await cancel_wish(session, wish, local_now(settings))
    await callback.message.answer(f"Отказ зафиксирован. Потенциально сохранено: {money(wish.estimated_price)}.")
    await callback.answer()


@router.callback_query(F.data.startswith("wait:menu:"))
async def wait_menu(callback: CallbackQuery) -> None:
    wish_id = callback.data.rsplit(":", 1)[1]
    await callback.message.answer(
        "На сколько продлить ожидание?",
        reply_markup=inline(
            [
                [("3 дня", f"wait:add:{wish_id}:3"), ("7 дней", f"wait:add:{wish_id}:7")],
                [("14 дней", f"wait:add:{wish_id}:14"), ("30 дней", f"wait:add:{wish_id}:30")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit:menu:"))
async def edit_menu(callback: CallbackQuery) -> None:
    wish_id = callback.data.rsplit(":", 1)[1]
    await callback.message.answer(
        "Что изменить?",
        reply_markup=inline(
            [
                [("Название", f"edit:field:{wish_id}:title"), ("Цена", f"edit:field:{wish_id}:price")],
                [("Тип", f"edit:field:{wish_id}:purchase_type"), ("Причина", f"edit:field:{wish_id}:reason")],
                [("Критерии", f"edit:field:{wish_id}:criteria")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit:field:"))
async def edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, wish_id, field = callback.data.split(":")
    if field == "purchase_type":
        await callback.message.answer(
            "Выбери новый тип:",
            reply_markup=inline(
                [
                    [("Необходимость", f"edit:type:{wish_id}:Необходимость")],
                    [("Улучшение", f"edit:type:{wish_id}:Улучшение")],
                    [("Просто хочется", f"edit:type:{wish_id}:Просто хочется")],
                ]
            ),
        )
        await callback.answer()
        return
    await state.set_state(EditWish.value)
    await state.update_data(wish_id=int(wish_id), field=field)
    prompt = "Напиши новое значение."
    if field == "price":
        prompt = "Напиши новую цену в рублях или «не знаю»."
    await callback.message.answer(prompt)
    await callback.answer()


@router.callback_query(F.data.startswith("edit:type:"))
async def edit_type(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, wish_id, value = callback.data.split(":", 3)
    wish = await get_user_wish(session, callback.from_user.id, int(wish_id))
    if wish:
        wish.purchase_type = value
        await callback.message.answer("Тип обновлён.")
    await callback.answer()


@router.message(EditWish.value)
async def edit_value(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    wish = await get_user_wish(session, message.from_user.id, data["wish_id"])
    if not wish:
        await state.clear()
        return
    field = data["field"]
    raw = clean_text(message.text or "", 500)
    if field == "title":
        wish.title = clean_text(raw, 200)
    elif field == "price":
        price = None if raw.lower() in {"не знаю", "нет", "-"} else parse_price(raw)
        if price is None and raw.lower() not in {"не знаю", "нет", "-"}:
            await message.answer("Цена должна быть больше нуля.")
            return
        await update_price_without_shortening_quarantine(wish, price)
    elif field == "reason":
        wish.reason = raw or None
    elif field == "criteria":
        wish.criteria = raw or None
    await state.clear()
    await message.answer("Изменения сохранены.")
