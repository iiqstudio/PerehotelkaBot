from datetime import datetime, timedelta

from app.services.quarantine import quarantine_duration, quarantine_until


def test_quarantine_duration_by_price() -> None:
    assert quarantine_duration(999) == timedelta(hours=24)
    assert quarantine_duration(1000) == timedelta(hours=24)
    assert quarantine_duration(5000) == timedelta(days=3)
    assert quarantine_duration(20000) == timedelta(days=7)
    assert quarantine_duration(50000) == timedelta(days=14)
    assert quarantine_duration(50001) == timedelta(days=30)
    assert quarantine_duration(None) == timedelta(days=7)


def test_quarantine_until_uses_created_at() -> None:
    created = datetime(2026, 9, 6, 12, 0)
    assert quarantine_until(created, 6000) == datetime(2026, 9, 13, 12, 0)
