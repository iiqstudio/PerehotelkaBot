from types import SimpleNamespace

from app.bot.middlewares.access import AccessMiddleware


class DummyMessage:
    def __init__(self) -> None:
        self.answers = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


async def test_access_denies_unknown_user() -> None:
    middleware = AccessMiddleware({1, 2})
    message = DummyMessage()
    called = False

    async def handler(_event, _data):
        nonlocal called
        called = True

    await middleware(handler, message, {"event_from_user": SimpleNamespace(id=3)})
    assert not called
    assert message.answers == ["Этот бот приватный. Доступ закрыт."]


async def test_access_allows_known_user() -> None:
    middleware = AccessMiddleware({1, 2})
    message = DummyMessage()
    called = False

    async def handler(_event, _data):
        nonlocal called
        called = True

    await middleware(handler, message, {"event_from_user": SimpleNamespace(id=1)})
    assert called
