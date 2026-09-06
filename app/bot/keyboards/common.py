from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="➕ Записать желание")],
        [KeyboardButton(text="⏳ На карантине"), KeyboardButton(text="✅ Готовы к решению")],
        [KeyboardButton(text="📦 Купленные"), KeyboardButton(text="❌ Отменённые")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⚙️ Настройки")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def inline(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows
        ]
    )
