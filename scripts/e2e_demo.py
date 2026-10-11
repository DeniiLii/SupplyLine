"""Сценарий показа для жюри (3 минуты), только клики в интерфейсе:
симулятор → лента счетов → продажа → попытка двойной продажи → +30 дней → просрочка → стресс якоря → ворота фазы 0.

Запуск: сервер на http://127.0.0.1:8000, затем python scripts/e2e_demo.py [base_url]
Перед прогоном демо сбрасывается (POST /api/demo/reset).
"""

from __future__ import annotations

import sys
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def step(n: int, text: str) -> None:
    print(f"{n}. {text}")


def main() -> None:
    urllib.request.urlopen(urllib.request.Request(BASE + "/api/demo/reset", method="POST")).read()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(BASE + "/simulator")
        expect(page.get_by_text("Дороже кредита МСП на")).to_be_visible()
        expect(page.get_by_text("19,67%").first).to_be_visible()
        step(1, "Симулятор: эффективная ставка 19,67% и честная плашка «Дороже кредита МСП»")

        page.get_by_role("link", name="Лента счетов").click()
        page.get_by_role("row", name="SL-2026-КРУПНЫЙ").click()
        expect(page.get_by_role("button", name="Продать счёт")).to_be_disabled()
        expect(page.get_by_role("alert").filter(has_text="Концентрация на одного якоря")).to_be_visible()
        step(2, "Крупный счёт: покупка заблокирована потолком концентрации 25% с объяснением правила")
        page.keyboard.press("Escape")

        page.get_by_role("tab", name="Предложения").click()
        rows = page.locator("tbody tr[data-clickable='true']")
        rows.nth(1).click()
        page.get_by_role("button", name="Продать счёт").click()
        expect(page.get_by_text("Счёт продан").first).to_be_visible(timeout=10_000)
        step(3, "Обычное предложение продано: требование уступлено, деньги придут в течение суток")

        page.get_by_role("button", name="Попытаться продать повторно").click()
        expect(page.get_by_text("двойное финансирование", exact=False).first).to_be_visible()
        step(4, "Попытка двойной продажи: реестр вернул 409, продажа заблокирована")

        number = page.get_by_role("dialog").get_by_role("heading").first.inner_text().replace("Счёт ", "").strip()
        page.keyboard.press("Escape")
        page.get_by_role("button", name="+1 день").first.click()
        expect(page.get_by_text("Часы переведены вперёд").first).to_be_visible()
        page.get_by_role("tab", name="Профинансированы").click()
        page.get_by_placeholder("Счёт, УПД или поставщик").fill(number)
        page.get_by_role("row", name=f"Счёт {number}").click()
        expect(page.get_by_role("dialog").get_by_text("Профинансирован").first).to_be_visible()
        page.get_by_role("button", name="Смоделировать просрочку якоря").click()
        expect(page.get_by_text("Якорь не оплатил в срок").first).to_be_visible()
        step(5, "+1 день: деньги у поставщика; смоделирован неплатёж якоря")
        page.keyboard.press("Escape")

        page.get_by_role("button", name="+30 дней").first.click()
        expect(page.get_by_text("Часы переведены вперёд").first).to_be_visible()
        page.get_by_role("tab", name="Просрочка и регресс").click()
        expect(page.locator("tbody").get_by_text("Регресс").first).to_be_visible()
        step(6, "+30 дней: просрочка 30 дней → регресс к поставщику")

        page.get_by_role("link", name="Портфельная модель").click()
        expect(page.get_by_text("Капитал под риск не покрывает дефолт якоря").first).to_be_visible()
        expect(page.get_by_text("16,4%").first).to_be_visible()
        step(7, "Стресс: дефолт якоря 25% даёт потери 1 033 млн ₽ против капитала 676; безопасная доля 16,4%")

        page.get_by_role("link", name="Обзор платформы").click()
        expect(page.get_by_text("Фаза 0: показатели ворот 1")).to_be_visible()
        expect(page.get_by_text("Время от акцепта до денег")).to_be_visible()
        step(8, "Ворота фазы 0: одобрения, просрочка 30+, фрод, время до денег, внешнее фондирование")

        assert not errors, errors
        b.close()
    urllib.request.urlopen(urllib.request.Request(BASE + "/api/demo/reset", method="POST")).read()
    print("Сценарий пройден кликами без ручной подготовки.")


if __name__ == "__main__":
    main()
