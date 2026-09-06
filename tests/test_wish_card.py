from datetime import datetime, timedelta

from app.bot.handlers.lists import wish_card
from app.config import Settings
from app.database.models import Wish, WishStatus


def test_wish_card_uses_human_status_label() -> None:
    now = datetime.now()
    wish = Wish(
        title="куртка на осень",
        estimated_price=11000,
        purchase_type="просто хочется",
        status=WishStatus.WAITING_FIRST_REVIEW.value,
        created_at=now,
        first_review_at=now + timedelta(hours=24),
        quarantine_until=now + timedelta(days=7),
        next_action_at=now + timedelta(hours=24),
    )

    text = wish_card(
        wish,
        Settings(
            bot_token="token",
            allowed_user_ids={1},
            timezone="Europe/Moscow",
            database_path="data/test.db",
        ),
    )

    assert "Статус: ожидает первой проверки" in text
    assert "waiting_first_review" not in text
