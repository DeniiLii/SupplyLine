"""Рендер слайдов презентации (секции 1920×1080) в PNG и векторный PDF.

python scripts/render_deck.py <папка deck с project/> <папка img> <выходная папка>
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

deck = Path(sys.argv[1]); img = Path(sys.argv[2]).resolve(); out = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)
index = json.loads((deck / "project" / "deck.json").read_text(encoding="utf-8"))
blobs = {"/_blob/262a471903df027a29af48f639286130": "sim.png",
         "/_blob/45981ebd0292b08b1e033d1a89e4da75": "card.png",
         "/_blob/729490f026777831496de4c1c54eb8c0": "model.png"}
slides = []
for sid in index["order"]:
    html = (deck / "project" / "slides" / f"{sid}.html").read_text(encoding="utf-8")
    for k, v in blobs.items():
        html = html.replace(k, (img / v).as_uri())
    slides.append(html)
fonts = "".join(f'<link rel="stylesheet" href="{f["href"]}">' for f in index["faces"].values())
css = """
@page { size: 1920px 1080px; margin: 0 }
html, body { margin: 0; padding: 0; background: #0B1222 }
section { position: relative; width: 1920px; height: 1080px; box-sizing: border-box; overflow: hidden;
          page-break-after: always; break-after: page; -webkit-print-color-adjust: exact; print-color-adjust: exact }
section:last-child { page-break-after: auto }
h1, h2, h3, p, ul, ol { margin: 0 }
aside { display: none }
table { border-collapse: collapse; width: 100% }
th, td { padding: 0.35em 0.6em; border-bottom: 1px solid #DDE2EA }
th { font-weight: 600; color: #4F586B; font-size: 0.85em }
"""
page_html = f'<!doctype html><html lang="ru"><head><meta charset="utf-8">{fonts}<style>{css}</style></head><body>{"".join(slides)}</body></html>'
tmp = out / "_deck_render.html"
tmp.write_text(page_html, encoding="utf-8")
notes = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(viewport={"width": 1920, "height": 1080})
    p.goto(tmp.as_uri(), wait_until="networkidle")
    p.wait_for_timeout(1500)
    secs = p.locator("section")
    for i in range(secs.count()):
        secs.nth(i).screenshot(path=str(out / f"slide-{i + 1:02d}.png"))
        notes.append(secs.nth(i).locator("aside").inner_text() if secs.nth(i).locator("aside").count() else "")
    p.pdf(path=str(out / "SupplyLine_pitch.pdf"), width="1920px", height="1080px", print_background=True)
    b.close()
(out / "notes.json").write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
tmp.unlink()
print(len(notes), "slides")
