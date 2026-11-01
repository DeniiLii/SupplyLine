"""Факты на экране «Рынок и допущения»: обязательные поля, ссылки, дата проверки (WP2)."""

import re

import pytest
from fastapi.testclient import TestClient

from api import content
from api.main import app

FIELDS = ("name", "value", "date", "status", "used_in")
STATUSES = {"Подтверждено", "Неточно", "Нет данных", "Опровергнут"}


@pytest.mark.parametrize("fact", content.FACTS, ids=lambda f: f["name"][:40])
def test_fact_fields(fact):
    for k in FIELDS:
        assert str(fact.get(k, "")).strip(), f"пустое поле {k}"
    assert fact["status"] in STATUSES
    if fact["source"] != content.INTERNAL_SOURCE:
        assert re.match(r"^https://[\w.-]+\.\w+/", fact["url"]), fact["url"]
    for u in fact.get("urls", []):
        assert u.startswith("https://")


def test_meta_has_date_and_no_unconfirmed():
    with TestClient(app) as c:
        m = c.get("/api/meta").json()
    assert m["facts_as_of"] == content.FACTS_AS_OF
    assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", m["facts_as_of"])
    assert all(f["status"] != "Не подтверждено" for f in m["facts"])


def test_key_rate_next_meeting_is_future():
    kr = next(f for f in content.FACTS if f["name"].startswith("Ключевая ставка"))
    assert "18.12.2026" in kr["date"] and "следующее заседание 23.10" not in kr["date"]


def test_market_estimate_checklist_done():
    item = next(c for c in content.CHECKLIST if c["item"].startswith("Размер рынка"))
    assert item["done"] and item["link"] == "docs/analytics/02_market_estimate.md"
