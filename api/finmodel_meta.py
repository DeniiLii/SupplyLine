"""Описание параметров финмодели для экрана и экспорта: подпись, единица, бейдж, источник, ячейка «Вводных»."""

from __future__ import annotations

import io
from pathlib import Path

import openpyxl

from engine.finmodel import FinParams

BOOK = Path(__file__).resolve().parents[1] / "docs" / "model" / "SupplyLine_financial_model.xlsx"

# key, подпись, единица, бейдж, источник, ячейка(и) «Вводных», группа
PARAMS: list[dict] = [
    dict(key="ks_now", label="Ключевая ставка сейчас", unit="pct", badge="Факт",
         source="Банк России, 14,00% с 27.07.2026", cell="B5", group="Макро"),
    dict(key="ks_scenario", label="Сценарий KС", unit="choice", badge="Гипотеза",
         source="1 константа · 2 смягчение · 3 шок +3 п.п.", cell="B6", group="Макро"),
    dict(key="ks_pass_through", label="Перенос KС в цену", unit="choice", badge="Гипотеза",
         source="1 цена пересчитывается · 2 цена по KС старта", cell="B7", group="Макро"),
    dict(key="scenario", label="Сценарий фондирования", unit="choice", badge="Гипотеза",
         source="A банк-партнёр · B кредитная линия · C ЦФА · M смешанный", cell="B33", group="Фондирование"),
    dict(key="price_mode", label="Режим цены", unit="choice", badge="Гипотеза",
         source="1 по формуле · 2 с потолком рынка", cell="B47", group="Цена и риск"),
    dict(key="t_days", label="Срок финансирования", unit="days", badge="Гипотеза",
         source="Допущение автора; диапазон 14–90", cell="B41", group="Цена и риск"),
    dict(key="lgd", label="LGD", unit="pct", badge="Гипотеза", source="Допущение автора", cell="B42",
         group="Цена и риск"),
    dict(key="cover", label="Страховое покрытие", unit="pct", badge="Гипотеза",
         source="0% в базе; в сделке Т-Банка дебиторка застрахована", cell="B43", group="Цена и риск"),
    dict(key="ins_rate", label="Тариф страхования", unit="pct", badge="Гипотеза", source="Допущение автора",
         cell="B44", group="Цена и риск"),
    dict(key="r_opex", label="r_opex в цене", unit="pct", badge="Гипотеза", source="Компонент цены", cell="B45",
         group="Цена и риск"),
    dict(key="r_margin", label="r_margin в цене", unit="pct", badge="Гипотеза", source="Компонент цены",
         cell="B46", group="Цена и риск"),
    dict(key="msp_rate", label="Кредит МСП до 1 года", unit="pct", badge="Факт",
         source="Банк России, июнь 2026", cell="B48", group="Цена и риск"),
    dict(key="speed_prem", label="Премия за скорость сверх кредита", unit="pct", badge="Гипотеза",
         source="Проверяется интервью с поставщиками", cell="B49", group="Цена и риск"),
    dict(key="loss_mult", label="Множитель реализованных потерь", unit="x", badge="Гипотеза",
         source="1 = потери равны ожидаемым", cell="B50", group="Цена и риск"),
    dict(key="retention", label="Удержание риска по внебалансу", unit="pct", badge="Гипотеза",
         source="Skin in the game", cell="B34", group="Риск и капитал"),
    dict(key="cfa_fee", label="Комиссия оператора ЦФА", unit="pct", badge="Гипотеза",
         source="Тариф нужно получить у партнёра", cell="B35", group="Риск и капитал"),
    dict(key="cap_norm", label="Норма капитала", unit="pct", badge="Гипотеза",
         source="Упрощённая норма", cell="B36", group="Риск и капитал"),
    dict(key="eq_switch", label="Капитал замещает заёмное фондирование", unit="bool", badge="Гипотеза",
         source="1 учитывать · 0 нет", cell="B37", group="Риск и капитал"),
    dict(key="coe", label="Требуемая доходность на капитал", unit="pct", badge="Гипотеза",
         source="Ориентир автора", cell="B38", group="Риск и капитал"),
    dict(key="tax", label="Налог на прибыль", unit="pct", badge="Факт",
         source="НК РФ, с 01.01.2025; перенос убытков без ограничения 50% — упрощение", cell="B39",
         group="Риск и капитал"),
    dict(key="turnover_bn", label="Оборот Г1–Г5", unit="bn", badge="Гипотеза",
         source="Концепция: Г1 5–10; Г3 40–60; Г5 120–200", cell="B59:F59", group="Объёмы"),
    dict(key="avg_invoice", label="Средний счёт", unit="mln", badge="Гипотеза", source="Допущение автора",
         cell="B62", group="Объёмы"),
    dict(key="var_pct", label="Переменные расходы от оборота", unit="pct", badge="Гипотеза",
         source="ЭДО, платежи, сверка", cell="B63", group="Объёмы"),
    dict(key="fte", label="Сотрудники Г1–Г5", unit="count", badge="Гипотеза", source="Около 50 в зрелости",
         cell="B65:F65", group="Постоянные расходы"),
    dict(key="it", label="ИТ и интеграции, ₽ млн", unit="mln", badge="Гипотеза", source="Допущение автора",
         cell="B66:F66", group="Постоянные расходы"),
    dict(key="comp", label="Комплаенс и юристы, ₽ млн", unit="mln", badge="Гипотеза", source="Допущение автора",
         cell="B67:F67", group="Постоянные расходы"),
    dict(key="mkt", label="Продажи и маркетинг, ₽ млн", unit="mln", badge="Гипотеза", source="Допущение автора",
         cell="B68:F68", group="Постоянные расходы"),
    dict(key="fte_cost", label="Стоимость сотрудника в месяц", unit="mln", badge="Гипотеза",
         source="С налогами, цены Г1", cell="B69", group="Постоянные расходы"),
    dict(key="fte_idx", label="Индексация стоимости сотрудника", unit="pct", badge="Гипотеза",
         source="Допущение автора", cell="B70", group="Постоянные расходы"),
    dict(key="ga", label="Прочие и общехозяйственные", unit="pct", badge="Гипотеза", source="Допущение автора",
         cell="B71", group="Постоянные расходы"),
    dict(key="stress_share", label="Доля крупнейшего якоря", unit="pct", badge="Гипотеза",
         source="Доля якоря в стресс-тесте книги (25%); лимит платформы — настройка anchor_cap, 15%", cell="B77", group="Стресс"),
    dict(key="stress_month", label="Месяц события", unit="month", badge="Гипотеза", source="Середина Г4",
         cell="B78", group="Стресс"),
]
CHOICE_ENCODE = {"scenario": lambda v: "ABCM".index(v) + 1}


def defaults() -> list[dict]:
    p = FinParams()
    out = []
    for m in PARAMS:
        v = getattr(p, m["key"])
        if isinstance(v, tuple):
            v = [float(x) for x in v]
        elif not isinstance(v, (int, str)):
            v = float(v)
        out.append({**m, "value": v})
    return out


def export_xlsx(p: FinParams) -> bytes:
    """Копия книги-эталона с подставленными во «Вводные» значениями.
    Пересчёт формул выполнит Excel при открытии (fullCalcOnLoad)."""
    wb = openpyxl.load_workbook(BOOK)
    ws = wb["Вводные"]
    for m in PARAMS:
        v = getattr(p, m["key"])
        enc = CHOICE_ENCODE.get(m["key"])
        if enc:
            v = enc(v)
        if ":" in m["cell"]:
            start, end = m["cell"].split(":")
            row = start[1:]
            cols = [chr(c) for c in range(ord(start[0]), ord(end[0]) + 1)]
            for c, x in zip(cols, v):
                ws[f"{c}{row}"] = float(x)
        else:
            ws[m["cell"]] = v if isinstance(v, (int, str)) else float(v)
    wb.calculation.fullCalcOnLoad = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
