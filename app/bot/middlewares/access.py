from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_user_ids: set[int]) -> None:
        self.allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user and user.id not in self.allowed_user_ids:
            if isinstance(event, Message) or hasattr(event, "answer"):
                await event.answer("Этот бот приватный. Доступ закрыт.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Этот бот приватный. Доступ закрыт.", show_alert=True)
            return None
        return await handler(event, data)
