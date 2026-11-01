"""Паритет движка с книгой docs/model/SupplyLine_financial_model.xlsx (кэшированные значения).

Сверяются листы «Месяцы», «Годы», «Сценарии», «Чувствит», «Стресс», «Ставки», «Юнит».
Допуск: 1e-6 относительный (и 1e-9 абсолютный около нуля).
Второй тест пересчитывает копии книги в LibreOffice с другими переключателями.
Без LibreOffice локально он пропускается с видимой причиной; в CI (переменная CI) отсутствие
LibreOffice — ошибка, чтобы 13 вариантов не «зеленели» молча.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from engine.finmodel import FinParams, run

BOOK = Path(__file__).resolve().parents[1] / "docs" / "model" / "SupplyLine_financial_model.xlsx"
COLS = "BCDEF"
SCEN_BLOCKS = {("A", 1): 11, ("A", 2): 34, ("B", 1): 57, ("B", 2): 80,
               ("C", 1): 103, ("C", 2): 126, ("M", 1): 149, ("M", 2): 172}
SCEN_ROWS = ["r_app", "income", "fund_net", "el_borne", "ins", "cfa_fee", "var_opex", "fix_opex",
             "pbt", "cum_pbt", "tax", "np", "cum_np", "capital_end", "eq_need_end", "eff", "margin",
             "per_bal", "cm", "breakeven_turnover"]
YEAR_ROWS = {3: "turnover", 4: "turnover_bn", 5: "invoices", 6: "avg_bal", 7: "bal_end", 8: "avg_last",
             9: "income", 10: "fund_gross", 11: "eq_benefit", 12: "fund_net", 13: "nii",
             14: "el_borne", 15: "ins", 16: "cfa_fee", 17: "var_opex", 18: "fix_opex", 19: "pbt",
             20: "tax", 21: "np", 22: "cum_np", 23: "capital_avg", 24: "rorc", 25: "econ",
             26: "cost_to_nii", 27: "nim", 28: "opex_to_turnover", 30: "r_app", 31: "eff",
             32: "msp", 33: "eff_minus_msp", 34: "margin", 35: "per_bal", 36: "cm",
             37: "breakeven_turnover"}
MONTH_COLS = {"E": "turnover", "F": "bal_end", "G": "avg", "H": "ks", "I": "r_app", "J": "r_fund",
              "K": "borne", "L": "w_cfa", "M": "prem_on", "N": "income", "O": "fund_gross",
              "P": "capital", "Q": "eq_benefit", "R": "fund_net", "S": "el_all", "T": "el_borne",
              "U": "ins", "V": "cfa_fee", "W": "var_opex", "X": "fix_opex", "Y": "pbt",
              "Z": "cum_pbt", "AA": "tax_cum", "AB": "tax", "AC": "np", "AD": "cum_np",
              "AE": "eq_need"}


class Diff:
    def __init__(self) -> None:
        self.rows: list[str] = []
        self.n = 0

    def eq(self, where: str, engine, excel) -> None:
        self.n += 1
        if excel in (None, "н/д", "нет в горизонте") or engine is None:
            if not (engine is None and excel in ("н/д", "нет в горизонте", None)):
                self.rows.append(f"{where}: движок {engine!r}, Excel {excel!r}")
            return
        a, b = float(engine), float(excel)
        if abs(a - b) > max(1e-9, 1e-6 * abs(b)):
            self.rows.append(f"{where}: движок {a!r}, Excel {b!r}")

    def assert_ok(self) -> None:
        assert self.n > 0
        assert not self.rows, f"{len(self.rows)} расхождений из {self.n}:\n" + "\n".join(self.rows[:40])


def compare_book(path: Path, p: FinParams) -> Diff:
    wb = openpyxl.load_workbook(path, data_only=True)
    res = run(p)
    dd = Diff()

    ms = wb["Месяцы"]
    for i, m in enumerate(res["months"]):
        for col, key in MONTH_COLS.items():
            dd.eq(f"Месяцы!{col}{i + 3}", m[key], ms[f"{col}{i + 3}"].value)

    gy = wb["Годы"]
    for row, key in YEAR_ROWS.items():
        for i, c in enumerate(COLS):
            dd.eq(f"Годы!{c}{row}", res["years"][i][key], gy[f"{c}{row}"].value)
    dd.eq("Годы!B29", res["years"][0]["off_balance_share"], gy["B29"].value)
    k = res["kpis"]
    dd.eq("Годы!B39", k["eq_need_peak"], gy["B39"].value)
    dd.eq("Годы!B40", k["eq_need_peak_month"], gy["B40"].value)
    dd.eq("Годы!B41", k["first_positive_np_month"], gy["B41"].value)
    dd.eq("Годы!B43", k["cum_np_bottom"], gy["B43"].value)
    dd.eq("Годы!B44", k["cum_pbt_5y"], gy["B44"].value)
    dd.eq("Годы!B45", k["breakeven_turnover_y5"], gy["B45"].value)
    dd.eq("Годы!B46", k["breakeven_share_y5"], gy["B46"].value)
    dd.eq("Годы!B47", k["sustained_positive_month"], gy["B47"].value)

    sc = wb["Сценарии"]
    for (s, mode), top in SCEN_BLOCKS.items():
        x = next(r for r in res["matrix"] if (r["scenario"], r["mode"]) == (s, mode))
        for j, key in enumerate(SCEN_ROWS, start=1):
            for i, c in enumerate(COLS):
                dd.eq(f"Сценарии!{c}{top + j} {s}{mode}", x["years"][i][key], sc[f"{c}{top + j}"].value)
    for idx, (s, mode) in enumerate(SCEN_BLOCKS):
        row = 3 + idx
        x = next(r for r in res["matrix"] if (r["scenario"], r["mode"]) == (s, mode))
        for i, c in enumerate("CDEFG"):
            dd.eq(f"Сценарии!{c}{row}", x["pbt"][i], sc[f"{c}{row}"].value)
        for c, key in zip("HIJKLMN", ("np5", "cum_np5", "eff5", "eff_minus_msp5", "margin5",
                                       "breakeven5", "eq_need")):
            dd.eq(f"Сценарии!{c}{row}", x[key], sc[f"{c}{row}"].value)
        assert x["verdict"] == sc[f"O{row}"].value

    se = wb["Чувствит"]
    s = res["sensitivity"]
    dd.eq("Чувствит!AJ43", s["base_pbt"], se["AJ43"].value)
    for i, r in enumerate(s["rows"]):
        row = 5 + i
        dd.eq(f"Чувствит!D{row}", r["delta_low"], se[f"D{row}"].value)
        dd.eq(f"Чувствит!E{row}", r["delta_high"], se[f"E{row}"].value)
        dd.eq(f"Чувствит!F{row}", r["pbt_low"], se[f"F{row}"].value)
        dd.eq(f"Чувствит!G{row}", r["pbt_high"], se[f"G{row}"].value)
        dd.eq(f"Чувствит!H{row}", r["range"], se[f"H{row}"].value)

    st = wb["Стресс"]
    x = res["stress"]
    for cell, key in {"B4": "month", "B5": "year", "B6": "bal", "B7": "share", "B8": "exposure",
                      "B9": "lgd", "B10": "cover", "B11": "gross", "B12": "borne", "B13": "loss",
                      "B14": "el_year", "B15": "unexpected", "B16": "capital", "B17": "coverage",
                      "B18": "np_year", "B19": "np_year_with_event", "B20": "eq_need_peak",
                      "B21": "eq_need_with_event", "B22": "max_share"}.items():
        dd.eq(f"Стресс!{cell}", x[key], st[cell].value)
    for i in range(5):
        for j, c in enumerate("BCDE"):
            dd.eq(f"Стресс!{c}{27 + i}", x["grid"][i][j], st[f"{c}{27 + i}"].value)
            dd.eq(f"Стресс!{c}{35 + i}", x["grid_cap"][i][j], st[f"{c}{35 + i}"].value)
    for i, r in enumerate(x["by_month"]):
        for c, key in zip("BCDE", ("bal", "capital", "loss", "coverage")):
            dd.eq(f"Стресс!{c}{44 + i}", r[key], st[f"{c}{44 + i}"].value)

    sv = wb["Ставки"]
    dd.eq("Ставки!B4", res["pd_port"], sv["B4"].value)
    dd.eq("Ставки!B5", res["el_rate"], sv["B5"].value)
    dd.eq("Ставки!B6", res["r_el"], sv["B6"].value)
    dd.eq("Ставки!B12", res["cap_discount"], sv["B12"].value)
    dd.eq("Ставки!B13", res["msp_discount"], sv["B13"].value)
    dd.eq("Ставки!B14", res["fund_ceiling"], sv["B14"].value)
    for c, v in zip("BCD", res["coefs"]):
        dd.eq(f"Ставки!B{8 + 'BCD'.index(c)}", v, sv[f"B{8 + 'BCD'.index(c)}"].value)
    gr = wb["Рост"]
    for i, c in enumerate("BCDEFG"):
        dd.eq(f"Рост!{c}7", res["nodes"][i], gr[f"{c}7"].value)
    rs = wb["Расходы"]
    for i, c in enumerate(COLS):
        dd.eq(f"Расходы!{c}11", res["fixed_opex"][i], rs[f"{c}11"].value)

    un = wb["Юнит"]
    order = [(un[f"{c}5"].value, 1 if un[f"{c}6"].value == "формула" else 2) for c in "BCDEFGHI"]
    for c, key in zip("BCDEFGHI", order):
        u = next(r for r in res["unit"]["all"] if (r["scenario"], r["mode"]) == key)
        for row, k2 in {7: "r", 8: "eff", 9: "D", 10: "recv", 11: "fund", 12: "el", 13: "opex",
                        14: "margin", 15: "margin_rate", 16: "margin_per_1000", 17: "msp_cost",
                        18: "overpay"}.items():
            dd.eq(f"Юнит!{c}{row}", u[k2], un[f"{c}{row}"].value)
        assert u["position"] == un[f"{c}19"].value
    return dd


def test_excel_parity_base():
    compare_book(BOOK, FinParams()).assert_ok()


# ---------------------------------------------------------------- LibreOffice


def _soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        if p := shutil.which(name):
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if Path(p).exists():
            return p
    return None


VARIANTS = [
    {"B33": 1}, {"B33": 2}, {"B33": 3}, {"B33": 4},
    {"B47": 2}, {"B33": 3, "B47": 2},
    {"B6": 2}, {"B6": 3}, {"B7": 2}, {"B6": 2, "B7": 2},
    {"B41": 30}, {"B41": 60}, {"B43": 0.5},
]
CELL_TO_PARAM = {"B33": ("scenario", lambda v: "ABCM"[v - 1]), "B47": ("price_mode", int),
                 "B6": ("ks_scenario", int), "B7": ("ks_pass_through", int),
                 "B41": ("t_days", Decimal), "B43": ("cover", lambda v: Decimal(str(v)))}


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: ",".join(f"{k}={x}" for k, x in v.items()))
def test_excel_parity_variants(variant):
    if _soffice() is None:
        if os.environ.get("CI"):
            pytest.fail("В CI нужен LibreOffice: без него варианты книги не пересчитываются")
        pytest.skip("LibreOffice не установлен: пересчёт вариантов книги пропущен (в CI обязателен)")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.xlsx"
        wb = openpyxl.load_workbook(BOOK)
        for cell, val in variant.items():
            wb["Вводные"][cell] = val
        wb.save(src)
        out = Path(tmp) / "out"
        subprocess.run([_soffice(), "--headless", "--calc", "--convert-to", "xlsx", "--outdir",
                        str(out), str(src)], check=True, capture_output=True, timeout=180)
        kw = {CELL_TO_PARAM[c][0]: CELL_TO_PARAM[c][1](v) for c, v in variant.items()}
        compare_book(out / "in.xlsx", FinParams(**kw)).assert_ok()
