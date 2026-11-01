"""Пакет аналитики для облачного диска: docs/analytics/*.md → PDF (Chromium, шрифт Inter с кириллицей) + книга v2.

Запуск: python scripts/export_analytics.py   (нужны playwright с chromium и пакет markdown)
Результат: deliverables/analytics/00_README.txt, 01–03 и 05 в PDF, 04_Финансовая_модель.xlsx (scripts/build_model_v2.py).
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools" / "pylib"))
sys.path.insert(0, str(ROOT))

import markdown  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

SRC = ROOT / "docs" / "analytics"
OUT = ROOT / "deliverables" / "analytics"
FONTS = ROOT / "web" / "node_modules" / "@fontsource" / "inter" / "files"
DOCS = [
    ("01_project_description.md", "01_Описание_проекта.pdf"),
    ("02_market_estimate.md", "02_Оценка_рынка.pdf"),
    ("03_implementation_plan.md", "03_План_внедрения_и_развития.pdf"),
    ("05_financial_model_summary.md", "05_Финансовая_модель_краткое_описание.pdf"),
]
DISCLAIMER = "Демо-прототип на синтетических данных. Не банк, не оферта, не работает с реальными деньгами."


def font_css() -> str:
    css = []
    for weight in (400, 600):
        for subset in ("cyrillic", "latin"):
            f = FONTS / f"inter-{subset}-{weight}-normal.woff2"
            if f.exists():
                b64 = base64.b64encode(f.read_bytes()).decode()
                css.append(f"@font-face{{font-family:Inter;font-weight:{weight};"
                           f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


CSS = """
@page { size: A4; margin: 18mm 16mm 20mm; }
body { font-family: Inter, 'Segoe UI', 'DejaVu Sans', sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1B2230; }
h1 { font-size: 20pt; line-height: 1.2; margin: 0 0 8pt; color: #1F3270; }
h2 { font-size: 13.5pt; margin: 18pt 0 6pt; color: #1F3270; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; break-after: avoid; }
p, li { margin: 4pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.5pt; break-inside: auto; }
th, td { border-bottom: 0.5pt solid #C4CAD6; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #EEF1F7; font-weight: 600; }
tr { break-inside: avoid; }
code { font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 9pt; background: #F2F4F8; padding: 0 2pt; }
.foot { margin-top: 18pt; padding-top: 6pt; border-top: 0.5pt solid #C4CAD6; font-size: 8.5pt; color: #5D6679; }
"""


def html(md_text: str, title: str) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "sane_lists"])
    return (f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{font_css()}{CSS}</style></head><body>{body}"
            f"<div class='foot'>SupplyLine · {DISCLAIMER} Выгрузка {date.today():%d.%m.%Y}.</div></body></html>")


def pdf_text_ok(pdf: Path) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        return "pdftotext не найден: текстовый слой не проверен"
    t = subprocess.run([exe, "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode("utf-8", "replace")
    cyr = sum(1 for ch in t if "а" <= ch.lower() <= "я")
    bad = t.count("�") + t.count("□")
    if cyr < 200 or bad:
        raise SystemExit(f"{pdf.name}: кириллица не читается (букв {cyr}, битых {bad})")
    return f"текстовый слой ОК: {cyr} кириллических букв"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        for src, name in DOCS:
            text = (SRC / src).read_text(encoding="utf-8")
            page.set_content(html(text, name), wait_until="load")
            page.evaluate("document.fonts.ready")
            out = OUT / name
            page.pdf(path=str(out), format="A4", print_background=True, display_header_footer=True,
                     header_template="<span></span>",
                     footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#5D6679'>"
                                     "<span class='pageNumber'></span> / <span class='totalPages'></span></div>",
                     margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"})
            print(f"{name}: {out.stat().st_size // 1024} КБ, {pdf_text_ok(out)}")
        b.close()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_model_v2.py")], check=True)
    files = sorted(p.name for p in OUT.iterdir() if p.suffix in (".pdf", ".xlsx"))
    (OUT / "00_README.txt").write_text(
        "SupplyLine · пакет аналитики Спринта №1\n"
        f"Дата выгрузки: {date.today():%d.%m.%Y}\n\n" + DISCLAIMER + "\n\nФайлы:\n"
        + "".join(f"  {f}\n" for f in files)
        + "\nЧисла пересчитываются из кода: scripts/export_numbers.py → numbers.json.\n"
          "Параметры с пометкой «Гипотеза» — допущения автора, проверяются интервью (Спринт №2).\n"
          "Книга 04 помечена «пересчитать при открытии»: Excel и LibreOffice пересчитают формулы сами.\n",
        encoding="utf-8")
    print("00_README.txt:", ", ".join(files))


if __name__ == "__main__":
    main()
