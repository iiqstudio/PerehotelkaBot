from html import escape
import re


MAX_TEXT = 500
MAX_TITLE = 200


def clean_text(value: str, limit: int = MAX_TEXT) -> str:
    return value.strip()[:limit]


def h(value: object) -> str:
    return escape(str(value), quote=False)


def parse_price(value: str) -> int | None:
    normalized = re.sub(r"[^\d]", "", value)
    if not normalized:
        return None
    price = int(normalized)
    return price if price > 0 else None


def money(value: int | None) -> str:
    if value is None:
        return "цена неизвестна"
    return f"{value:,}".replace(",", " ") + " ₽"
