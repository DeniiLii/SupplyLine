"""Сценарий показа для жюри (3 минуты), только клики в интерфейсе:
симулятор → лента счетов → продажа → попытка двойной продажи → +30 дней → просрочка → стресс якоря → ворота фазы 0.

Запуск: сервер на http://127.0.0.1:8000, затем python scripts/e2e_demo.py [base_url]
Перед прогоном демо сбрасывается (POST /api/demo/reset). Те же шаги вызывает tests/test_e2e_jury.py.
"""

from __future__ import annotations

import sys

from playwright.sync_api import expect, sync_playwright


def run(base: str, step=lambda n, text: print(f"{n}. {text}")) -> None:
    """Проходит 8 шагов показа кликами. Падает AssertionError/TimeoutError при любом расхождении."""
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page = ctx.new_page()
        # Сброс через браузер: в режиме песочницы он сбрасывает именно эту сессию (cookie)
        page.request.post(base + "/api/demo/reset")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(base + "/simulator")
        expect(page.get_by_text("Дороже кредита МСП на")).to_be_visible()
        expect(page.get_by_text("19,67%").first).to_be_visible()
        step(1, "Симулятор: эффективная ставка 19,67% и честная плашка «Дороже кредита МСП»")

        page.get_by_role("link", name="Лента счетов").click()
        page.get_by_role("row", name="SL-2026-КРУПНЫЙ").click()
        expect(page.get_by_role("button", name="Продать счёт")).to_be_disabled()
        expect(page.get_by_role("alert").filter(has_text="Концентрация на одного якоря: не больше 15%")).to_be_visible()
        step(2, "Крупный счёт заблокирован потолком концентрации 15% с объяснением правила")
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
        expect(page.get_by_text("Книга Excel, доля якоря 25%: капитал не покрывает дефолт").first).to_be_visible()
        expect(page.get_by_text("Капитал покрывает дефолт якоря при лимите 15%").first).to_be_visible()
        expect(page.get_by_text("16,4%").first).to_be_visible()
        step(7, "Стресс: при доле 25% капитал не покрывает дефолт якоря, при лимите платформы 15% покрывает")

        page.get_by_role("link", name="Обзор платформы").click()
        expect(page.get_by_text("Фаза 0: показатели ворот 1")).to_be_visible()
        expect(page.get_by_text("Время от акцепта до денег")).to_be_visible()
        step(8, "Ворота фазы 0: одобрения, просрочка 30+, фрод, время до денег, внешнее фондирование")

        assert not errors, errors
        page.request.post(base + "/api/demo/reset")
        b.close()


def main() -> None:
    run(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
    print("Сценарий пройден кликами без ручной подготовки.")


if __name__ == "__main__":
    main()
