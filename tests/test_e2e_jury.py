"""Сценарий жюри кликами в браузере (Playwright). По умолчанию не запускается: pytest -m e2e."""

import pytest

from scripts.e2e_demo import run
from tests.server import ROOT, live_server

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(not (ROOT / "web" / "dist" / "index.html").exists(), reason="Нужен собранный web/dist")
@pytest.mark.parametrize("sandbox", ["0", "1"])
def test_jury_scenario(sandbox):
    steps: list[int] = []
    with live_server(SUPPLYLINE_SANDBOX=sandbox) as base:
        run(base, step=lambda n, _text: steps.append(n))
    assert steps == list(range(1, 9))


@pytest.mark.skipif(not (ROOT / "web" / "dist" / "index.html").exists(), reason="Нужен собранный web/dist")
def test_tour_keyboard():
    """Тур открывается с клавиатуры, шаги переключаются, Esc закрывает; при открытой карточке счёта панель остаётся доступной."""
    from playwright.sync_api import expect, sync_playwright

    with live_server() as base, sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page.goto(base + "/simulator")
        btn = page.get_by_role("button", name="Показать за 3 минуты").first
        btn.focus()
        page.keyboard.press("Enter")
        panel = page.get_by_role("dialog", name="Цена за секунду")
        expect(panel).to_be_visible()
        expect(panel.get_by_text("Шаг 1 из 8")).to_be_visible()
        panel.get_by_role("button", name="Дальше").click()
        expect(page.get_by_role("heading", name="Крупный счёт упирается в лимит")).to_be_visible()
        # Карточка счёта открылась, панель тура доступна (не скрыта модальным диалогом)
        expect(page.get_by_role("dialog", name="Счёт SL-2026-КРУПНЫЙ")).to_be_visible(timeout=10_000)
        expect(page.get_by_role("button", name="Назад")).to_be_enabled()
        page.get_by_role("button", name="Назад").click()
        page.get_by_role("heading", name="Цена за секунду").focus()
        page.keyboard.press("Escape")
        expect(page.get_by_text("Шаг 1 из 8")).to_be_hidden()
        b.close()
