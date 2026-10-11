"""Скриншоты всех экранов (1440×900 и 390×844), ошибки консоли и проверка axe-core.

Запуск: сервер на http://127.0.0.1:8000 (python tasks.py demo), затем python scripts/screenshots.py
Результат: screenshots/*.png, screenshots/report.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
AXE = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

SCREENS = [
    ("01-simulator", "/simulator", "organizer"),
    ("02-feed", "/feed", "organizer"),
    ("03-overview", "/overview", "organizer"),
    ("04-model", "/model", "organizer"),
    ("05-market", "/market", "organizer"),
    ("06-supplier", "/supplier", "supplier"),
    ("07-anchor", "/anchor", "anchor"),
    ("08-investor", "/investor", "investor"),
    ("09-about", "/about", "organizer"),
]
VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}


def main() -> int:
    OUT.mkdir(exist_ok=True)
    report: dict = {"console_errors": {}, "axe": {}}
    axe_src = AXE.read_text(encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vname, (w, h) in VIEWPORTS.items():
            for theme in (["light", "dark"] if vname == "desktop" else ["light"]):
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="ru-RU",
                                          reduced_motion="reduce")
                ctx.add_init_script(f"localStorage.setItem('sl-theme', '{theme}')")
                page = ctx.new_page()
                errors: list[str] = []
                page.on("console", lambda m, errors=errors: m.type == "error" and errors.append(m.text))
                page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                for name, path, role in SCREENS:
                    page.add_init_script(f"localStorage.setItem('sl-role', '{role}')")
                    page.goto(BASE + path, wait_until="networkidle")
                    page.wait_for_timeout(900)
                    suffix = f"{vname}" + ("" if theme == "light" else "-dark")
                    page.screenshot(path=str(OUT / f"{name}-{suffix}.png"), full_page=True)
                    if vname == "desktop" and theme == "light":
                        page.add_script_tag(content=axe_src)
                        res = page.evaluate(
                            "async () => (await axe.run(document, {runOnly: {type: 'tag', values: "
                            "['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations"
                            ".map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,"
                            " targets: v.nodes.slice(0,3).map(n => n.target.join(' '))}))")
                        report["axe"][name] = res
                # Карточка счёта (диалог) — отдельный снимок
                if theme == "light":
                    page.goto(BASE + "/feed", wait_until="networkidle")
                    page.wait_for_timeout(500)
                    page.locator("tbody tr[data-clickable='true']:visible, ul li button.panel:visible").first.click()
                    page.wait_for_timeout(1200)
                    page.screenshot(path=str(OUT / f"10-invoice-card-{vname}.png"), full_page=False)
                report["console_errors"][f"{vname}-{theme}"] = errors
                ctx.close()
        browser.close()
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    n_err = sum(len(v) for v in report["console_errors"].values())
    serious = {k: [v for v in vs if v["impact"] in ("serious", "critical")] for k, vs in report["axe"].items()}
    print(f"Ошибок консоли: {n_err}")
    for k, vs in serious.items():
        for v in vs:
            print(f"axe {k}: {v['impact']} {v['id']} ×{v['nodes']} — {v['help']} {v['targets']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
