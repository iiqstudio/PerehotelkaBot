from aiogram import Router

from app.bot.handlers import add_wish, lists, purchase, reviews, settings, start, statistics


def build_router() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(add_wish.router)
    router.include_router(lists.router)
    router.include_router(reviews.router)
    router.include_router(purchase.router)
    router.include_router(statistics.router)
    router.include_router(settings.router)
    return router
