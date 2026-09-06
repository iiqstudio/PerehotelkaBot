from aiogram.fsm.state import State, StatesGroup


class AddWish(StatesGroup):
    title = State()
    price = State()
    purchase_type = State()
    reason = State()
    current_alternative = State()
    confirm = State()


class Consequence(StatesGroup):
    text = State()


class Criteria(StatesGroup):
    text = State()


class OptionForm(StatesGroup):
    name = State()
    price = State()
    url = State()
    comment = State()


class PurchaseForm(StatesGroup):
    final_price = State()
    rating_comment = State()


class EditWish(StatesGroup):
    value = State()
