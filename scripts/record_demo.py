"""Видео-демо 2–3 минуты: Playwright проходит тур «Показать за 3 минуты» с субтитрами и пишет MP4.

Запуск (сервер уже работает, для реальных пауз лучше SUPPLYLINE_MOCK_LATENCY=1):
    python scripts/record_demo.py http://127.0.0.1:8000 [--repo URL] [--demo URL] [--out deliverables/SupplyLine_demo.mp4]

ffmpeg берётся из PATH, переменной FFMPEG или пакета imageio-ffmpeg. Без звука; текст для озвучки — docs/VIDEO_SCRIPT.md.
После записи из MP4 снимаются 6 кадров (каждые 20 с) в deliverables/video_frames/ для проверки глазами.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
W, H = 1440, 900

# Субтитры по шагам тура: тот же порядок, что web/src/copy/ru.ts → tour.steps и docs/VIDEO_SCRIPT.md
SUBS = [
    "1/8 · Симулятор: цена от риска якоря. Продажа счёта дороже кредита МСП, и экран это пишет",
    "2/8 · Крупный счёт упирается в потолок концентрации 15%: продажа недоступна, правило видно",
    "3/8 · Обычный счёт: УПД найден, акцепт есть, лимиты в норме. Требование продано и попало в реестр",
    "4/8 · Повторная продажа того же требования: реестр отказывает, двойного финансирования нет",
    "5/8 · +1 день: деньги у поставщика. Моделируем неплатёж якоря в срок",
    "6/8 · +30 дней: просрочка переходит в регресс к поставщику по договору",
    "7/8 · Стресс-тест: при доле якоря 25% капитала не хватает, при лимите платформы 15% хватает",
    "8/8 · Ворота фазы 0: одобрения, просрочка, фрод, время до денег, внешнее фондирование",
]

OVERLAY_JS = """
window.__sub = (text) => {
  let el = document.getElementById('__sub');
  if (!el) {
    el = document.createElement('div');
    el.id = '__sub';
    el.style.cssText = 'position:fixed;left:24px;bottom:24px;max-width:860px;z-index:2147483647;padding:12px 16px;' +
      'border-radius:10px;background:rgba(11,18,34,.86);color:#fff;font:500 20px/1.35 Inter,system-ui,sans-serif;' +
      'pointer-events:none';
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.style.display = text ? 'block' : 'none';
};
window.__card = (title, lines) => {
  let el = document.getElementById('__card');
  if (!title) { if (el) el.remove(); return; }
  if (!el) {
    el = document.createElement('div');
    el.id = '__card';
    el.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;flex-direction:column;justify-content:center;' +
      'padding:0 120px;background:#0F1B3D;color:#fff;font:400 24px/1.5 Inter,system-ui,sans-serif';
    document.body.appendChild(el);
  }
  el.innerHTML = '';
  const h = document.createElement('div');
  h.style.cssText = 'font:600 52px/1.15 Inter,system-ui,sans-serif;margin-bottom:28px';
  h.textContent = title;
  el.appendChild(h);
  for (const l of lines) { const p = document.createElement('div'); p.textContent = l; p.style.opacity = '.9'; el.appendChild(p); }
};
"""


def ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    sys.path.insert(0, str(ROOT / ".tools" / "pylib"))
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("Нужен ffmpeg: PATH, переменная FFMPEG или pip install imageio-ffmpeg")


def pause(page: Page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def tour(page: Page):
    return page.locator("[data-tour]")


def sub(page: Page, text: str) -> None:
    page.evaluate("t => window.__sub(t)", text)


def click_tour(page: Page, name: str) -> None:
    tour(page).get_by_role("button", name=name, exact=True).click()


def wait_idle(page: Page) -> None:
    # «Выполнить шаг» блокирует кнопки, пока идёт запрос
    expect(tour(page).get_by_role("button", name="Дальше").or_(tour(page).get_by_role("button", name="Завершить"))).to_be_enabled(timeout=20_000)


def scroll(page: Page, px: int, steps: int = 4) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, px / steps)
        pause(page, 0.35)


def record(base: str, repo: str, demo: str, out: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="sl-video-"))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, locale="ru-RU", record_video_dir=str(tmp),
                            record_video_size={"width": W, "height": H}, color_scheme="light")
        ctx.add_init_script(OVERLAY_JS)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Тёмный фон с первого кадра, пока грузится приложение
        page.set_content('<body style="margin:0;background:#0F1B3D"></body>')
        page.request.post(base + "/api/demo/reset")
        page.goto(base + "/simulator")
        page.evaluate("() => window.__card('SupplyLine', ['Цифровой реверсивный факторинг для среднего бизнеса', "
                      "'Показ за 3 минуты · синтетические данные'])")
        pause(page, 4)
        page.evaluate("() => window.__card(null)")

        page.get_by_role("button", name="Показать за 3 минуты").first.click()
        expect(tour(page)).to_be_visible()
        wait_idle(page)

        # 1. Симулятор
        sub(page, SUBS[0])
        expect(page.get_by_text("Дороже кредита МСП на")).to_be_visible()
        pause(page, 6)
        scroll(page, 500)
        pause(page, 5)
        page.mouse.wheel(0, -2000)
        pause(page, 1.5)

        # 2. Крупный счёт
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[1])
        expect(page.get_by_role("alert").filter(has_text="Концентрация на одного якоря")).to_be_visible(timeout=15_000)
        pause(page, 12)

        # 3. Продажа обычного счёта
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[2])
        pause(page, 3)
        click_tour(page, "Выполнить шаг")
        wait_idle(page)
        expect(tour(page).get_by_role("status")).to_contain_text("продан")
        pause(page, 10)

        # 4. Повторная продажа
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[3])
        pause(page, 2.5)
        click_tour(page, "Выполнить шаг")
        wait_idle(page)
        expect(tour(page).get_by_role("status")).to_contain_text("заблокировано")
        pause(page, 9)

        # 5. +1 день и неплатёж
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[4])
        pause(page, 2.5)
        click_tour(page, "Выполнить шаг")
        wait_idle(page)
        expect(tour(page).get_by_role("status")).to_contain_text("просрочке")
        pause(page, 10)

        # 6. +30 дней: регресс
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[5])
        pause(page, 2.5)
        click_tour(page, "Выполнить шаг")
        wait_idle(page)
        expect(tour(page).get_by_role("status")).to_contain_text("регресс")
        pause(page, 10)

        # 7. Стресс-тест
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[6])
        expect(page.get_by_text("Капитал покрывает дефолт якоря при лимите").first).to_be_visible(timeout=15_000)
        pause(page, 12)

        # 8. Ворота фазы 0
        click_tour(page, "Дальше")
        wait_idle(page)
        sub(page, SUBS[7])
        expect(page.get_by_text("Время от акцепта до денег").first).to_be_visible(timeout=15_000)
        pause(page, 12)

        sub(page, "")
        page.evaluate("([r, d]) => window.__card('SupplyLine', ['Демо-прототип на синтетических данных. Не банк, не оферта, "
                      "не работает с реальными деньгами.', 'Все компании вымышлены.', '', 'Код: ' + r, 'Демо: ' + d])",
                      [repo, demo])
        pause(page, 6)
        assert not errors, errors
        video = page.video.path() if page.video else None
        ctx.close()
        b.close()
    if not video:
        sys.exit("Playwright не записал видео")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    return out


def frames(mp4: Path) -> list[Path]:
    d = mp4.parent / "video_frames"
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.png"):
        p.unlink()
    subprocess.run([ffmpeg(), "-loglevel", "error", "-i", str(mp4), "-vf", "fps=1/20,scale=960:-1", "-frames:v", "8",
                    str(d / "frame_%02d.png")], check=True)
    return sorted(d.glob("*.png"))


def duration(mp4: Path) -> float:
    r = subprocess.run([ffmpeg(), "-i", str(mp4)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:8000")
    ap.add_argument("--repo", default="ссылка в описании решения")
    ap.add_argument("--demo", default="ссылка в описании решения")
    ap.add_argument("--out", default=str(ROOT / "deliverables" / "SupplyLine_demo.mp4"))
    a = ap.parse_args()
    t = time.time()
    mp4 = record(a.base, a.repo, a.demo, Path(a.out))
    dur, size = duration(mp4), mp4.stat().st_size / 1e6
    fr = frames(mp4)
    print(f"{mp4}: {dur:.0f} с, {size:.1f} МБ, кадров для проверки: {len(fr)} (запись {time.time() - t:.0f} с)")
    if not 120 <= dur <= 180:
        print("Внимание: длительность вне 2:00–3:00")
    if size > 100:
        print("Внимание: файл больше 100 МБ")


if __name__ == "__main__":
    main()
