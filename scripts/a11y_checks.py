"""Проверки доступности сверх axe: цели нажатия, фокус с клавиатуры, диалог, масштаб 200%.

Запуск: сервер на http://127.0.0.1:8000, затем python scripts/a11y_checks.py [base]
"""

from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PAGES = ["/simulator", "/feed", "/overview", "/model", "/market", "/supplier", "/anchor", "/investor", "/about"]

SMALL_TARGETS = """() => {
  const sel = 'button, a[href], input, select, [role=tab], [role=switch], [role=slider], [tabindex="0"]';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (el.closest('table')) continue;           // строки таблиц — вся строка как цель
    if (el.matches('[tabindex="0"]') && !el.matches('button,a,input,select')) {
      if (el.classList.contains('hint-term') || el.matches('div.overflow-x-auto, div.overflow-auto, span')) continue;
    }
    if (r.height < 24 || r.width < 24) out.push(`${el.tagName} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}" ${Math.round(r.width)}×${Math.round(r.height)}`);
  }
  return out;
}"""


def main() -> None:
    rep: dict = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        for path in PAGES:
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(600)
            small = page.evaluate(SMALL_TARGETS)
            # Обход с клавиатуры: 40 нажатий Tab, у каждого фокуса должно быть видимое кольцо
            no_ring = []
            seen = 0
            for _ in range(40):
                page.keyboard.press("Tab")
                info = page.evaluate("""() => { const e = document.activeElement; if (!e || e === document.body) return null;
                  const s = getComputedStyle(e); return {tag: e.tagName, name: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 30),
                  ring: s.boxShadow !== 'none' || (s.outlineStyle !== 'none' && s.outlineWidth !== '0px')}; }""")
                if info:
                    seen += 1
                    if not info["ring"]:
                        no_ring.append(f"{info['tag']} {info['name']}")
            rep[path] = {"small_targets": small[:10], "focus_steps": seen, "focus_without_ring": sorted(set(no_ring))[:10]}
        # Диалог: фокус внутри, Esc закрывает, фокус возвращается
        page.goto(BASE + "/feed", wait_until="networkidle")
        row = page.locator("tbody tr[data-clickable='true']").first
        row.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        inside = page.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        for _ in range(30):
            page.keyboard.press("Tab")
        still = page.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        page.keyboard.press("Escape")  # первое Esc закрывает открытую подсказку, если она есть
        page.wait_for_timeout(200)
        if page.locator("[role=dialog]").count():
            page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        closed = page.locator("[role=dialog]").count() == 0
        rep["dialog"] = {"focus_moves_in": inside, "focus_trapped_after_30_tabs": still, "escape_closes": closed}
        # Масштаб 200%: эквивалент окна 720 px
        page.set_viewport_size({"width": 720, "height": 900})
        zoom = {}
        for path in PAGES:
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(400)
            zoom[path] = page.evaluate("document.documentElement.scrollWidth")
        rep["zoom200_scroll_width"] = zoom
        b.close()
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
