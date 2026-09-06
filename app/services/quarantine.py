from datetime import datetime, timedelta


def quarantine_duration(price: int | None) -> timedelta:
    if price is None:
        return timedelta(days=7)
    if price <= 1000:
        return timedelta(hours=24)
    if price <= 5000:
        return timedelta(days=3)
    if price <= 20000:
        return timedelta(days=7)
    if price <= 50000:
        return timedelta(days=14)
    return timedelta(days=30)


def first_review_time(created_at: datetime) -> datetime:
    return created_at + timedelta(hours=24)


def quarantine_until(created_at: datetime, price: int | None) -> datetime:
    return created_at + quarantine_duration(price)


def days_label(delta: timedelta) -> str:
    total_seconds = max(0, int(delta.total_seconds()))
    if total_seconds < 86400:
        hours = max(1, (total_seconds + 3599) // 3600)
        return f"{hours} ч."
    days = (total_seconds + 86399) // 86400
    return f"{days} дн."
