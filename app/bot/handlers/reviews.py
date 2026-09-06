from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import inline
from app.bot.states.add_wish import Consequence, Criteria
from app.config import Settings
from app.services.text import clean_text, money
from app.services.time import local_now
from app.services.wish_service import (
    answer_first_review,
    cancel_wish,
    extend_wait,
    get_user_wish,
    save_consequence,
    start_research,
)

router = Router()


@router.callback_query(F.data.startswith("review:no:"))
async def review_no(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if not wish:
        await callback.answer("Не найдено", show_alert=True)
        return
    await answer_first_review(session, wish, "no", local_now(settings))
    await callback.message.answer(
        f"Отлично, импульс прошёл. В потенциально сохранённые деньги добавлено {money(wish.estimated_price)}."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("review:unsure:"))
async def review_unsure(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if not wish:
        await callback.answer("Не найдено", show_alert=True)
        return
    await answer_first_review(session, wish, "unsure", local_now(settings))
    await callback.message.answer("Оставляю покупку в карантине до основного срока.")
    await callback.answer()


@router.callback_query(F.data.startswith("review:yes:"))
async def review_yes(callback: CallbackQuery, state: FSMContext) -> None:
    wish_id = int(callback.data.rsplit(":", 1)[1])
    await state.set_state(Consequence.text)
    await state.update_data(wish_id=wish_id)
    await callback.message.answer(
        "Что случится, если ты вообще не купишь эту вещь?",
        reply_markup=inline(
            [
                [("Возникнет реальная проблема", f"consequence:{wish_id}:Возникнет реальная проблема")],
                [("Будет менее удобно", f"consequence:{wish_id}:Будет менее удобно")],
                [("Ничего особенного", f"consequence:{wish_id}:Ничего особенного")],
                [("Хочу ответить текстом", f"consequence_text:{wish_id}")],
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("consequence_text:"))
async def consequence_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Consequence.text)
    await state.update_data(wish_id=int(callback.data.rsplit(":", 1)[1]))
    await callback.message.answer("Напиши ответ одним сообщением.")
    await callback.answer()


@router.callback_query(F.data.startswith("consequence:"))
async def consequence_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    _, wish_id, text = callback.data.split(":", 2)
    wish = await get_user_wish(session, callback.from_user.id, int(wish_id))
    if wish:
        await save_consequence(session, wish, text, local_now(settings))
        await callback.message.answer("Ответ сохранён. Желание продолжает карантин.")
    await state.clear()
    await callback.answer()


@router.message(Consequence.text)
async def consequence_message(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    data = await state.get_data()
    wish = await get_user_wish(session, message.from_user.id, data["wish_id"])
    if wish:
        await save_consequence(session, wish, clean_text(message.text or ""), local_now(settings))
        await message.answer("Ответ сохранён. Желание продолжает карантин.")
    await state.clear()


@router.callback_query(F.data.startswith("decision:start:"))
async def decision_start(callback: CallbackQuery, state: FSMContext) -> None:
    wish_id = int(callback.data.rsplit(":", 1)[1])
    await state.set_state(Criteria.text)
    await state.update_data(wish_id=wish_id)
    await callback.message.answer(
        "Запиши главные требования к покупке. Например: цена до 10 000 ₽, вес до 3 кг, подходит для шерсти животных."
    )
    await callback.answer()


@router.message(Criteria.text)
async def criteria_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    wish = await get_user_wish(session, message.from_user.id, data["wish_id"])
    if wish:
        await start_research(wish, clean_text(message.text or ""))
        await message.answer(
            "Можно начинать поиск. Старайся выбирать только по записанным критериям и не добавлять в корзину товары из рекомендаций.",
            reply_markup=inline(
                [
                    [("Я выбрал варианты", f"option:add:{wish.id}")],
                    [("Вернусь позже", f"noop:{wish.id}"), ("Отказаться", f"wish:cancel:{wish.id}")],
                ]
            ),
        )
    await state.clear()


@router.callback_query(F.data.startswith("decision:cancel:"))
async def decision_cancel(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    wish = await get_user_wish(session, callback.from_user.id, int(callback.data.rsplit(":", 1)[1]))
    if wish:
        await cancel_wish(session, wish, local_now(settings))
        await callback.message.answer("Отказ зафиксирован.")
    await callback.answer()


@router.callback_query(F.data.startswith("wait:add:"))
async def wait_add(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    _, _, wish_id, days = callback.data.split(":")
    wish = await get_user_wish(session, callback.from_user.id, int(wish_id))
    if wish:
        await extend_wait(wish, int(days), local_now(settings))
        await callback.message.answer(f"Ок, вернусь через {days} дней.")
    await callback.answer()


@router.callback_query(F.data.startswith("noop:"))
async def noop(callback: CallbackQuery) -> None:
    await callback.answer("Хорошо.")
