"""PPTX из отрендеренных слайдов: по картинке 16:9 на слайд и заметки докладчика."""
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

src = Path(sys.argv[1]); out = Path(sys.argv[2])
notes = json.loads((src / "notes.json").read_text(encoding="utf-8"))
prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 13,333 × 7,5 дюйма, 16:9
prs.core_properties.title = "SupplyLine — питч"
prs.core_properties.author = "Команда SupplyLine"
blank = prs.slide_layouts[6]
for i, note in enumerate(notes, 1):
    s = prs.slides.add_slide(blank)
    pic = s.shapes.add_picture(str(src / f"slide-{i:02d}.png"), 0, 0, prs.slide_width, prs.slide_height)
    pic.name = f"Слайд {i}"
    s.notes_slide.notes_text_frame.text = note
prs.save(out)
print("saved", out, len(notes))
