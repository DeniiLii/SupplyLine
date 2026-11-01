"""Презентация Спринта №1: редактируемый PPTX из нативных объектов PowerPoint (текст, таблицы, фигуры).

Запуск: python scripts/build_deck.py [--repo URL] [--demo URL] [--pdf]
Числа берутся только из deliverables/numbers.json (scripts/export_numbers.py). Скриншоты — screenshots/*.png.
Визуальный язык прежней колоды (presentation/source): синий #1F3270, светлый #F5F7FC, шрифт Golos Text.
--pdf экспортирует PDF через PowerPoint (Windows) или LibreOffice, если он есть.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[1]
NUM = json.loads((ROOT / "deliverables" / "numbers.json").read_text(encoding="utf-8"))
SHOTS = ROOT / "screenshots"
OUT = ROOT / "deliverables" / "SupplyLine_pitch_sprint1.pptx"

FONT = "Golos Text"
NAVY, LIGHT, INK, GRAY = "1F3270", "F5F7FC", "141B2D", "4F586B"
SOFT, ACCENT, DANGER, OK = "B9C8E8", "8EA5D6", "F59A92", "7DD3A0"
DANGER_INK, OK_INK = "B3261E", "17663A"
PX = 6350  # EMU на пиксель макета 1920×1080


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def px(v: float) -> Emu:
    return Emu(int(v * PX))


# ---------------------------------------------------------------- форматирование чисел (как в интерфейсе)


def n(x: float, d: int = 0) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if x < 0 else "") + s


def sn(x: float, d: int = 0) -> str:
    return ("+" if x > 0 else "") + n(x, d)


def pc(x: float, d: int = 1) -> str:
    return n(x * 100, d) + "%"


# ---------------------------------------------------------------- примитивы


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = px(1920), px(1080)
        self.layout = self.prs.slide_layouts[6]
        self.count = 0

    def slide(self, dark: bool, notes: str, footer: str = ""):
        s = self.prs.slides.add_slide(self.layout)
        self.count += 1
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(NAVY if dark else LIGHT)
        s.notes_slide.notes_text_frame.text = notes
        fg = SOFT if dark else GRAY
        if self.count > 1:
            text(s, 128, 990, 1500, 40, footer or "SupplyLine", 24, fg)
            text(s, 1700, 990, 92, 40, str(self.count), 24, fg, align=PP_ALIGN.RIGHT)
        return s

    def save(self, out: Path) -> Path:
        out.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(out)
        return out


def text(s, x, y, w, h, value, size, color, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, lines=None):
    """Текстовое поле; size — в пикселях макета (1 px = 0,5 pt). lines — список (текст, размер, цвет, жирный)."""
    tb = s.shapes.add_textbox(px(x), px(y), px(w), px(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    rows = lines or [(value, size, color, bold)]
    for i, (t, sz, col, b) in enumerate(rows):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(sz * 0.25)
        r = p.add_run()
        r.text = t
        r.font.name, r.font.size, r.font.bold = FONT, Pt(sz / 2), b
        r.font.color.rgb = rgb(col)
    return tb


def title(s, value: str, dark: bool, y: int = 110, w: int = 1664) -> None:
    text(s, 128, y, w, 140, value, 56, LIGHT if dark else INK, bold=True)


def box(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sh = s.shapes.add_shape(shape, px(x), px(y), px(w), px(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    if line:
        sh.line.color.rgb = rgb(line)
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = min(0.5, 16 / max(1, min(w, h)))
    sh.shadow.inherit = False
    return sh


def big(s, x, y, w, value, label, color, label_color, size=120):
    text(s, x, y, w, size + 10, value, size, color, bold=True)
    text(s, x, y + size + 24, w, 90, label, 28, label_color)


def table(s, x, y, w, rows: list[list[str]], widths: list[int], dark: bool, size=26, row_h=64,
          tones: dict[tuple[int, int], str] | None = None):
    shape = s.shapes.add_table(len(rows), len(rows[0]), px(x), px(y), px(w), px(row_h * len(rows)))
    t = shape.table
    for j, cw in enumerate(widths):
        t.columns[j].width = px(cw)
    head_bg, body_bg = ("2A3F85", NAVY) if dark else ("E3E8F3", "FFFFFF")
    fg = LIGHT if dark else INK
    for i, row in enumerate(rows):
        t.rows[i].height = px(row_h)
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb(head_bg if i == 0 else body_bg)
            c.margin_left = c.margin_right = px(14)
            c.margin_top = c.margin_bottom = px(6)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame
            tf.text = ""
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
            r = p.add_run()
            r.text = val
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size / 2), i == 0
            r.font.color.rgb = rgb((tones or {}).get((i, j), fg))
    return shape


def viewport(path: Path, h_ratio: float = 900 / 1440) -> Path:
    """Скриншоты экранов — во всю высоту страницы; на слайд идёт первый экран (1440×900)."""
    from PIL import Image

    out = ROOT / "deliverables" / "deck_img" / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as im:
        im.crop((0, 0, im.width, min(im.height, int(im.width * h_ratio)))).save(out)
    return out


def picture(s, path: Path, x, y, w=None, h=None):
    if not path.exists():
        box(s, x, y, w or 600, h or 400, "E3E8F3")
        return
    s.shapes.add_picture(str(path), px(x), px(y), px(w) if w else None, px(h) if h else None)


# ---------------------------------------------------------------- слайды


def build(repo: str, demo_url: str) -> Path:
    fm, mk, dm, ts = NUM["finmodel"], NUM["market"], NUM["demo"], NUM["tests"]
    y = fm["years"]
    k = fm["kpis"]
    st25, st15 = fm["stress_book_25"], fm["stress_platform_15"]
    sim = dm["simulator_default"]
    cap = dm["anchor_cap"]
    d = Deck()

    # 1. Обложка
    s = d.slide(True, "Денис (капитан). SupplyLine даёт поставщику среднего бизнеса деньги за сутки после того, как "
                      "крупный покупатель подтвердил счёт. Цена считается по риску покупателя. За 5 минут: проблема, "
                      "механика, честная экономика, риски, работающий прототип и результаты Спринта №1.")
    text(s, 128, 110, 900, 60, "SupplyLine", 40, SOFT, bold=True)
    text(s, 128, 230, 1100, 260, "<24 часа", 200, LIGHT, bold=True)
    text(s, 128, 500, 1300, 120, "от акцепта крупного покупателя до денег у поставщика", 48, LIGHT)
    text(s, 128, 650, 1500, 60, "Цифровой реверсивный факторинг для среднего бизнеса с выручкой 0,8–2 млрд ₽", 32, SOFT)
    text(s, 128, 900, 1664, 60, "Егор Маркелов, Денис Липинский (капитан), Анна Якимович, Анна Кошелева · Спринт №1, "
                                f"{dm['facts_as_of']}", 26, SOFT)

    # 2. Проблема
    s = d.slide(False, "Анна Якимович (ресёрч). Сегмент: средние компании с выручкой 0,8–2 млрд ₽, их около 24 тысяч "
                       "в реестре МСП. Они ждут оплаты месяц-три, кредит МСП стоит около 18% и требует залога. Рынок "
                       "факторинга большой, но клиентов у факторов становится меньше: рост идёт за счёт крупных сделок.")
    title(s, "Поставщик отгрузил товар, а деньги придут через месяц-три", False)
    f = mk["facts"]
    for i, (v, lab, src) in enumerate([
        ("30–90", "дней отсрочки у крупных покупателей в рознице и промышленности", "в продуктовой рознице 8–40 дней, 381-ФЗ"),
        (pc(sim["msp_rate"]), "ставка кредита МСП до года, плюс залог и дни на одобрение", "Банк России, июнь 2026"),
        (n(f["factoring_portfolio_bn_2026_07_01"] / 1000, 2) + " трлн",
         f"₽ портфель факторинга; активных клиентов {n(f['factoring_active_clients_h1_2026'])}, −6% за год",
         "АФК на 01.07.2026, пересказ Финмаркета"),
    ]):
        x = 128 + i * 576
        big(s, x, 330, 540, v, lab, NAVY, INK, size=104)
        text(s, x, 640, 520, 80, src, 24, GRAY)

    # 3. Рынок снизу вверх (новый)
    sc = mk["scenarios"]
    s = d.slide(False, "Анна Якимович. Публичной цифры дебиторки средних компаний перед крупными покупателями нет, "
                       "поэтому считаем снизу вверх: предприятия × доля продающих крупным покупателям × выручка × доля "
                       "выручки. План 5-го года — 2–13% ёмкости по обороту, но охват поставщиков высокий: 26–51%. "
                       "Это главное, что проверяют интервью.",
                "Гипотезы автора, проверяются интервью (Спринт №2)")
    title(s, f"План 5-го года — {pc(sc['high']['plan_share'])}–{pc(sc['low']['plan_share'])} ёмкости сегмента по обороту", False)
    rows = [["Сценарий", "Доля с крупными покупателями", "Выручка, млрд ₽", "Доля выручки", "Ёмкость, млрд ₽ в год",
             "Доля плана Г5", "Охват поставщиков"]]
    names = {"low": "Низкий", "base": "Базовый", "high": "Высокий"}
    for key in ("low", "base", "high"):
        v = sc[key]
        rows.append([names[key], pc(v["a"], 0), n(v["R_bn"], 1), pc(v["b"], 0), n(v["sam_bn"]),
                     pc(v["plan_share"]), pc(v["coverage"])])
    tones = {(1, 6): DANGER_INK}
    table(s, 128, 300, 1664, rows, [220, 300, 220, 200, 260, 220, 244], False, tones=tones)
    p5 = mk["plan_y5"]
    text(s, 128, 600, 1664, 300, "", 30, INK, lines=[
        (f"Ёмкость = {n(mk['N'])} средних предприятий × доля × выручка × доля выручки. План 5-го года: "
         f"{n(p5['turnover_bn'])} млрд ₽ оборота, {n(p5['suppliers'])} поставщиков, {n(p5['anchors'])} якорей.", 30, INK, False),
        (f"Оборот на поставщика {n(mk['turnover_per_supplier_mln'])} млн ₽ в год, на якоря "
         f"{n(mk['turnover_per_anchor_bn'], 1)} млрд ₽. {n(p5['suppliers'])} поставщиков — "
         f"{pc(mk['suppliers_vs_active_clients'], 0)} всех активных клиентов факторов сегодня.", 30, INK, False),
        ("В низком сценарии охват больше половины сегмента недостижим: нужен порог МСП 3,5 млрд ₽ "
         "(в обсуждении) или поставщики вне сегмента.", 30, DANGER_INK, False),
    ])

    # 4. Решение
    s = d.slide(True, "Егор Маркелов (бизнес-аналитик). Пять шагов. Ключевое: акцепт покупателя — условие сделки, "
                      "поэтому цена считается по его риску, а скоринг поставщика влияет только на лимит.")
    title(s, "Сделка проходит за сутки, цена считается по риску покупателя", True)
    steps = [("УПД в ЭДО", "поставщик отгрузил и выпустил документ"), ("Акцепт", "покупатель подтвердил, что заплатит"),
             ("Предложение", "дисконт по формуле, без ручных согласований"),
             ("Деньги", "требование уступлено, выплата в течение суток"), ("Оплата", "покупатель платит в срок")]
    line = s.shapes.add_connector(1, px(160), px(400), px(1760), px(400))
    line.line.color.rgb, line.line.width = rgb(ACCENT), Pt(2)
    for i, (h, t) in enumerate(steps):
        x = 128 + i * 340
        c = box(s, x + 16, 384, 32, 32, LIGHT, shape=MSO_SHAPE.OVAL)
        c.line.color.rgb = rgb(ACCENT)
        text(s, x, 450, 310, 50, h, 34, LIGHT, bold=True)
        text(s, x, 510, 300, 150, t, 28, SOFT)
    text(s, 128, 760, 1600, 120, "Скоринг поставщика влияет только на его лимит. Просрочка покупателя ведёт к "
                                 "напоминаниям и регрессу к поставщику по договору.", 30, LIGHT)

    # 5. Три проверки
    s = d.slide(False, "Анна Кошелева (тестирование). Главный фрод в факторинге — двойная уступка. Три проверки до "
                       "покупки; в демо реестр отклонил все повторные продажи.")
    title(s, "Счёт покупается только после трёх проверок", False)
    for i, (h, t) in enumerate([("УПД найден в ЭДО", "Отгрузка подтверждена документом у оператора, а не словами поставщика"),
                                ("Покупатель акцептовал", "Крупный покупатель сам подтвердил обязательство заплатить в срок"),
                                ("Требования нет в реестре", "Ключ SHA-256 от покупателя, поставщика, номера, даты и суммы. "
                                                             "Повтор отклоняется")]):
        x = 128 + i * 560
        box(s, x, 290, 520, 420, "FFFFFF", line="D5DCEA")
        text(s, x + 40, 320, 100, 110, str(i + 1), 96, NAVY, bold=True)
        text(s, x + 40, 440, 440, 100, h, 34, INK, bold=True)
        text(s, x + 40, 560, 440, 140, t, 28, GRAY)
    text(s, 128, 780, 1664, 80, f"В демо заблокировано {dm['overview']['duplicates_blocked']} попыток продать один счёт "
                                "дважды. Потери от двойного финансирования: 0 ₽.", 32, INK, bold=True)

    # 6. Цена
    s = d.slide(False, "Денис Липинский (финансы). Говорим прямо: при фондировании около ключевой ставки дисконт не "
                       f"ниже краткосрочного кредита. Ставка на номинал {pc(sim['r_total'])} складывается из фондирования, "
                       "ожидаемых потерь, издержек и маржи. Поставщик платит за скорость и отсутствие залога.")
    title(s, f"Цена по формуле дороже кредита МСП на {n(sim['over_msp_pp'], 2)} п.п.", False)
    big(s, 128, 300, 760, pc(sim["eff_rate"], 2), "эффективная ставка поставщика при KС 14% и банке-партнёре", NAVY, INK, 150)
    big(s, 1000, 330, 700, pc(sim["msp_rate"]), "кредит МСП до года, Банк России, июнь 2026", GRAY, INK, 120)
    comp = sim["components"]
    for i, (lab, v) in enumerate([("Фондирование", pc(comp["funding"])), ("Ожидаемые потери", pc(comp["loss"])),
                                  ("Издержки", pc(comp["opex"])), ("Маржа", pc(comp["margin"]))]):
        text(s, 128 + i * 300, 640, 280, 110, "", 28, INK, lines=[(v, 44, NAVY, True), (lab, 26, GRAY, False)])
    text(s, 128, 800, 1600, 90, "За что платит поставщик: деньги за сутки, без залога и без лимита банка на себя. "
                                "Состав ставки на номинал — гипотезы, кроме KС.", 28, INK)

    # 7. Фондирование
    m = fm["matrix"]
    s = d.slide(True, "Денис. Четыре сценария фондирования. Если ограничить цену рынком, прибыль в 5-й год остаётся "
                      "только у банка-партнёра. ЦФА дорогие: премия 4,5 п.п. к ключевой.",
                "Финансовая модель, базовые параметры. Гипотезы, не прогноз")
    title(s, "Кто даёт деньги, определяет, сходится ли экономика", True)
    rows = [["Сценарий фондирования", "Ставка поставщика", "Прибыль, 5-й год", "С потолком рынка", "Капитал"]]
    labels = {"A": "A · банк-партнёр, KС + 1", "B": "B · кредитная линия, KС + 2,5", "C": "C · ЦФА для инвесторов, KС + 4,5",
              "M": "M · смешанная структура"}
    tones = {}
    for i, key in enumerate("ABCM", 1):
        rows.append([labels[key], pc(m[f"{key}1"]["eff5"], 2), sn(m[f"{key}1"]["np5"]), sn(m[f"{key}2"]["np5"]),
                     n(m[f"{key}1"]["eq_need"])])
        for j, v in ((2, m[f"{key}1"]["np5"]), (3, m[f"{key}2"]["np5"])):
            tones[(i, j)] = DANGER if v < 0 else LIGHT
    table(s, 128, 290, 1664, rows, [624, 260, 260, 280, 240], True, size=30, row_h=84, tones=tones)
    text(s, 128, 760, 1600, 90, f"Если ограничить цену рынком (не выше {pc(fm['params']['cap_rate'], 0)}), прибыль в "
                                "5-й год остаётся только у банка-партнёра. Суммы в млн ₽.", 30, LIGHT)

    # 8. Модель
    s = d.slide(False, f"Денис. Модель на 60 месяцев: оборот растёт с {n(y[0]['turnover_bn'])} до {n(y[4]['turnover_bn'])} "
                       f"млрд ₽ в год. Прибыль появляется в 5-й год, накопленный результат {n(k['cum_np_5y'])} млн ₽. "
                       "Модель совпадает с Excel-книгой, это проверяют тесты.",
                "Сценарий M, цена по формуле, KС 14%, срок 45 дней. Совпадает с Excel-моделью")
    title(s, "Прибыль появляется в 5-й год, окупаемости за 5 лет нет", False)
    for i, (v, lab, col) in enumerate([
        (sn(y[4]["pbt"]), "млн ₽ прибыли до налога в 5-й год", NAVY),
        (n(k["cum_np_5y"]), "млн ₽ накопленной чистой прибыли за 5 лет", DANGER_INK),
        (n(k["eq_need_peak"]), "млн ₽ собственного капитала на пике", NAVY),
        (n(k["breakeven_turnover_y5"] / 1000), f"млрд ₽ оборота для безубыточности, {pc(k['breakeven_share_y5'], 0)} плана Г5", NAVY),
    ]):
        big(s, 128 + i * 420, 320, 400, v, lab, col, INK, 88)
    rows = [["", *[f"Г{r['year']}" for r in y]],
            ["Оборот, млрд ₽", *[n(r["turnover_bn"]) for r in y]],
            ["Чистая прибыль, млн ₽", *[n(r["np"]) for r in y]],
            ["Накопленная, млн ₽", *[n(r["cum_np"]) for r in y]]]
    table(s, 128, 620, 1664, rows, [464, 240, 240, 240, 240, 240], False, size=26, row_h=58)

    # 9. Рычаги окупаемости (новый)
    lv = {x["key"]: x for x in fm["levers"]}
    s = d.slide(True, "Денис. Что нужно, чтобы модель окупилась, не меняя формул. Банк-партнёр плюс средний срок 60 дней "
                      "дают окупаемость к концу 5-го года; маржа 3,5% ускоряет её, но цена для поставщика уходит выше "
                      "потолка рынка. Срок и маржа зависят от якорей — это гипотезы для интервью.",
                "Пресеты экрана «Портфельная модель». Гипотезы, проверяются интервью")
    title(s, "Окупаемость в горизонте дают срок и банк-партнёр, маржа — ценой поставщика", True)
    rows = [["Пресет", "Окупаемость", "Накопленная ЧП, 5 лет", "Пик капитала", "Ставка поставщика, Г5"]]
    tones = {}
    for i, key in enumerate(("base", "bank", "t60", "m35"), 1):
        x = lv[key]
        rows.append([x["name"] + (" · " + x["note"] if key != "base" else " · M, 45 дней, маржа 2,4%"),
                     f"месяц {x['payback_month']}" if x["payback_month"] else "нет", sn(x["cum_np_5y"]),
                     n(x["eq_need_peak"]), pc(x["eff5"], 2)])
        tones[(i, 2)] = DANGER if x["cum_np_5y"] < 0 else OK
        tones[(i, 4)] = DANGER if x["above_cap"] else LIGHT
    table(s, 128, 290, 1664, rows, [704, 240, 280, 200, 240], True, size=26, row_h=84, tones=tones)
    text(s, 128, 760, 1600, 120, f"Потолок рынка {pc(fm['params']['cap_rate'], 0)}: кредит МСП + 1 п.п. за скорость. "
                                 "Ставки выше потолка отмечены красным: поставщик может уйти к кредиту.", 30, LIGHT)

    # 10. Драйверы
    rows_s = fm["sensitivity_pbt5"]["rows"]
    s = d.slide(False, "Денис. Торнадо по 11 драйверам. Три главных рычага: срок финансирования, оборот 5-го года и маржа. "
                       "Ключевая ставка переносится в цену, поэтому влияет слабо.",
                "Каждый драйвер меняется отдельно, остальные на базе")
    title(s, "Срок, оборот и маржа весят больше ключевой ставки", False)
    order = sorted(rows_s.values(), key=lambda r: -r["range_half"])[:7]
    mx = max(r["range_half"] for r in order)
    for i, r in enumerate(order):
        yy = 290 + i * 84
        text(s, 128, yy, 640, 60, r["name"], 28, INK, anchor=MSO_ANCHOR.MIDDLE)
        mid = 1180
        lo, hi = r["delta_low"], r["delta_high"]
        for v in (lo, hi):
            wv = abs(v) / mx * 420
            box(s, mid if v > 0 else mid - wv, yy + 12, max(wv, 2), 36, "1E8A4C" if v > 0 else "C0392B",
                shape=MSO_SHAPE.RECTANGLE)
        lab = f"±{n(r['range_half'])}" if abs(abs(lo) - abs(hi)) < 0.5 else f"{sn(min(lo, hi))} / {sn(max(lo, hi))}"
        text(s, 1620, yy, 172, 60, lab, 28, INK, bold=True, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 128, 890, 1664, 60, f"Изменение прибыли до налога 5-го года, млн ₽, база {sn(fm['sensitivity_pbt5']['base_pbt'])}. "
                                "Зелёный — рост, красный — падение.", 26, GRAY)

    # 11. Стресс: два состояния (обновлён)
    s = d.slide(True, f"Егор или Денис. Самый опасный риск — концентрация. Если покупатель с четвертью портфеля не платит, "
                      f"организатор теряет {n(st25['loss'])} млн ₽ при капитале {n(st25['capital'])} млн ₽. Безопасная доля "
                      f"{pc(st25['max_share'])}. В Спринте №1 лимит концентрации в продукте стал {pc(cap, 0)}: при нём "
                      "капитал покрывает потерю.",
                "Стресс-тест финансовой модели, сценарий M, месяц 42, LGD 60%")
    title(s, f"Лимит {pc(cap, 0)} на покупателя закрывает риск, который не выдерживала доля 25%", True)
    for i, (stt, head) in enumerate([(st25, f"Книга Excel: доля покупателя {pc(st25['share'], 0)}"),
                                     (st15, f"Платформа: лимит {pc(st15['share'], 0)}")]):
        x = 128 + i * 852
        good = stt["covered"]
        box(s, x, 290, 812, 520, "2A3F85", line=OK if good else DANGER)
        text(s, x + 48, 320, 720, 50, head, 32, SOFT, bold=True)
        text(s, x + 48, 400, 720, 130, n(stt["loss"]), 120, OK if good else DANGER, bold=True)
        text(s, x + 48, 540, 720, 50, f"млн ₽ потерь против {n(stt['capital'])} млн ₽ капитала", 28, LIGHT)
        text(s, x + 48, 640, 720, 120, ("Капитал покрывает дефолт" if good else "Капитал не покрывает дефолт")
             + f": покрытие {n(stt['coverage'], 2)}×", 34, OK if good else DANGER, bold=True)
    text(s, 128, 860, 1664, 80, f"Безопасная доля одного покупателя по модели — {pc(st25['max_share'])}. Лимит в "
                                "платформе — настройка; книга сохраняет 25% для паритета с Excel.", 28, SOFT)

    # 12. Прототип
    s = d.slide(False, f"Анна Кошелева (тестирование и разработка). Python-движок, API, база и интерфейс для четырёх ролей. "
                       f"{ts['unit']} автотестов и {ts['e2e']} браузерных сценария; сценарий показа проходится кликами "
                       "и встроен в интерфейс кнопкой «Показать за 3 минуты».",
                "ЭДО, акцепт, платежи и оператор ЦФА — имитации с теми же интерфейсами")
    title(s, "Прототип работает на синтетических данных", False)
    for x, name in ((128, "01-simulator-desktop.png"), (992, "04-model-desktop.png")):
        if (SHOTS / name).exists():
            box(s, x - 2, 278, 804, 504, "D5DCEA", shape=MSO_SHAPE.RECTANGLE)
            picture(s, viewport(SHOTS / name), x, 280, w=800)
    text(s, 128, 810, 800, 120, "Симулятор показывает цену и пишет, когда она выше кредита", 28, INK)
    text(s, 992, 810, 800, 120, "Модель: рычаги окупаемости и стресс при лимите платформы", 28, INK)

    # 13. Результаты Спринта №1 (новый)
    vid = NUM.get("video", {})
    s = d.slide(True, "Денис. Что сделано за спринт, каждое число проверяемо: тесты в CI, публичное демо с песочницей "
                      "на посетителя, видео на случай недоступности демо, закрыто противоречие лимита и стресс-теста, "
                      "факты обновлены, аналитика собрана.",
                "Результаты Спринта №1")
    title(s, "Результаты Спринта №1", True)
    mins = int(vid.get("seconds", 0) // 60)
    secs = int(vid.get("seconds", 0) % 60)
    items = [
        (f"{ts['unit']} + {ts['e2e']}", "автотестов и браузерных сценариев; CI: линтер, типы, сборка, e2e, Docker"),
        ("Демо", f"публичная ссылка с песочницей на посетителя: {demo_url}"),
        (f"{mins}:{secs:02d}", "видео-демо: 8 шагов тура «Показать за 3 минуты»"),
        (pc(cap, 0), f"лимит на покупателя вместо 25%: стресс-тест покрыт ({n(st15['coverage'], 2)}×)"),
        ("Факты", f"обновлены на {dm['facts_as_of']}: ставка ЦБ 23.10, данные АФК; {dm['facts_count']} фактов со ссылкой и статусом"),
        ("4 + 1", "документа аналитики и Excel-модель v2 без ошибок, с листом «Проверки»"),
    ]
    for i, (v, lab) in enumerate(items):
        col, row = i % 2, i // 2
        x, yy = 128 + col * 852, 280 + row * 210
        text(s, x, yy, 300, 90, v, 56, LIGHT if i != 3 else OK, bold=True)
        text(s, x + 320, yy + 6, 500, 180, lab, 28, SOFT)

    # 14. Дорожная карта
    s = d.slide(False, "Егор. Каждая фаза открывается только после ворот. Фаза 0 — цифровой факторинг без ЦФА с "
                       "банком-партнёром; метрики ворот 1 уже считаются на экране «Обзор платформы».")
    title(s, "Каждая фаза открывается только после ворот", False)
    phases = [("Фаза 0 · 0–6 мес", "Цифровой факторинг без ЦФА", "3–5 покупателей, 30–50 поставщиков",
               "Ворота: просрочка в норме, фрод ≈ 0, деньги < 24 ч"),
              ("Фаза 1 · 6–18 мес", "ЦФА через партнёра", "Внешние инвесторы через модельный SPV",
               "Ворота: внешнее фондирование > 30%"),
              ("Фаза 2 · 18–36 мес", "Вторичный рынок", "ML-скоринг на накопленной истории", "Ворота: объём для ликвидности"),
              ("Фаза 3 · 36+ мес", "Внешняя торговля", "Экспериментальные правовые режимы", "Ворота: регулирование допускает")]
    for i, (h, t, d1, g) in enumerate(phases):
        x = 128 + i * 420
        box(s, x, 290, 390, 560, "FFFFFF", line="D5DCEA")
        text(s, x + 32, 320, 330, 520, "", 28, INK, lines=[(h, 26, GRAY, True), (t, 36, NAVY, True), (d1, 28, INK, False),
                                                          (g, 26, GRAY, False)])

    # 15. Команда
    s = d.slide(True, "Денис. Представляем команду.")
    title(s, "Команда", True)
    for i, (nm, role) in enumerate([("Денис Липинский", "капитан, финансовый аналитик"),
                                    ("Егор Маркелов", "системный и бизнес-аналитик"),
                                    ("Анна Якимович", "ресёрч-аналитик"), ("Анна Кошелева", "тестировщик, программист")]):
        x = 128 + (i % 2) * 852
        yy = 300 + (i // 2) * 240
        text(s, x, yy, 800, 200, "", 28, LIGHT, lines=[(nm, 48, LIGHT, True), (role, 30, SOFT, False)])

    # 16. Что дальше (новый)
    s = d.slide(False, "Денис. Спринт №2 проверяет гипотезы, на которых держится экономика: готовность платить сверх "
                       "кредита, срок, маржу, долю выручки у крупных покупателей. И закрывает юридическую схему.",
                "Демо-прототип на синтетических данных. Не банк, не оферта, не работает с реальными деньгами")
    title(s, "Что дальше: Спринт №2", False)
    for i, (h, t) in enumerate([
        ("Интервью", "15 покупателей и 30 поставщиков: готовность платить сверх кредита МСП, срок, доля выручки"),
        ("Письма о намерениях", "банк-партнёр, оператор ЦФА, страховщик"),
        ("Юридическая схема ЦФА", "эмитент (фактор или SPV), обеспечение и страхование"),
        ("API акцепта", "готовность покупателей подтверждать счета через API или портал"),
    ]):
        yy = 290 + i * 150
        box(s, 128, yy + 14, 20, 20, NAVY, shape=MSO_SHAPE.OVAL)
        text(s, 180, yy, 1600, 140, "", 28, INK, lines=[(h, 36, INK, True), (t, 28, GRAY, False)])
    text(s, 128, 900, 1664, 50, f"Код: {repo}", 24, GRAY)
    return d.save(OUT)


def to_pdf(pptx: Path) -> Path | None:
    pdf = pptx.with_suffix(".pdf")
    if sys.platform == "win32":
        ps = (f"$p = New-Object -ComObject PowerPoint.Application; "
              f"$d = $p.Presentations.Open('{pptx}', $true, $false, $false); "
              f"$d.SaveAs('{pdf}', 32); $d.Close(); $p.Quit()")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        if r.returncode == 0 and pdf.exists():
            return pdf
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if exe:
        subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)], check=True)
        return pdf
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="ссылка в форме отправки")
    ap.add_argument("--demo", default="ссылка в форме отправки")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    out = build(a.repo, a.demo)
    print(f"{out}: {len(Presentation(out).slides)} слайдов")
    if a.pdf:
        pdf = to_pdf(out)
        print(pdf or "PDF не создан: нет PowerPoint и LibreOffice")


if __name__ == "__main__":
    main()
