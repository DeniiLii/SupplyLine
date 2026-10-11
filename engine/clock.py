"""Виртуальные часы демо. Время хранится в БД; здесь чистые функции."""

from __future__ import annotations

from datetime import datetime, timedelta

DEMO_START = datetime(2026, 10, 12, 9, 0)


def advance(now: datetime, days: int = 0, hours: int = 0) -> datetime:
    if days < 0 or hours < 0:
        raise ValueError("Часы идут только вперёд")
    return now + timedelta(days=days, hours=hours)
