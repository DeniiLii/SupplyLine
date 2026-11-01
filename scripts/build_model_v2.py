"""Книга v2 для пакета аналитики: исправленные #REF! (Годы!B42, Месяцы!F3, Сводка!A33:A40) и лист «Проверки» (19 тождеств, как engine/finmodel.py::checks).

Запуск: python scripts/build_model_v2.py [--out deliverables/analytics/04_Финансовая_модель.xlsx] [--recalc]
Исходник docs/model/SupplyLine_financial_model.xlsx не меняется. openpyxl не считает формулы: книга помечена
«пересчитать при открытии». С флагом --recalc (нужен LibreOffice) книга пересчитывается и проверяется на ошибки.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "model" / "SupplyLine_financial_model.xlsx"
OUT = ROOT / "deliverables" / "analytics" / "04_Финансовая_модель.xlsx"

# Месяц окупаемости = первый месяц с накопленной ЧП > 0 (решение 7 в docs/DECISIONS.md)
PAYBACK = ('=IFERROR(INDEX(Месяцы!$A$3:$A$62,MATCH(TRUE,INDEX(Месяцы!$AD$3:$AD$62>0,0),0)),'
           '"нет в горизонте")')
# Блок выбранного сценария на листе «Сценарии»: A1, A2, B1, B2, C1, C2, M1, M2; строка ПДН = начало + 9
SCEN_PBT = ("OFFSET(Сценарии!$B$1,CHOOSE((Вводные!$B$33-1)*2+Вводные!$B$47,11,34,57,80,103,126,149,172)+8,0,1,5)")

CHECKS = [
    ("Сумма долей рейтингов = 100%", "=ABS(SUM(Вводные!B53:B56)-1)<1E-9"),
    ("Веса источников A = 100%", "=ABS(Вводные!B25-1)<1E-9"),
    ("Веса источников B = 100%", "=ABS(Вводные!C25-1)<1E-9"),
    ("Веса источников C = 100%", "=ABS(Вводные!D25-1)<1E-9"),
    ("Веса источников M = 100%", "=ABS(Вводные!E25-1)<1E-9"),
    ("Узлы траектории неотрицательны", "=MIN(Рост!B7:G7)>=0"),
    ("Сумма месяцев = годовой оборот", "=SUMPRODUCT(ABS(Годы!B3:F3-Вводные!B59:F59*1000))<1E-6"),
    ("ПДН лет = накопленная ПДН месяцев", "=ABS(SUM(Годы!B19:F19)-Месяцы!Z62)<1E-6"),
    ("Налог за 5 лет = ставка × max(0, накопленная ПДН)", "=ABS(SUM(Месяцы!AB3:AB62)-Вводные!B39*MAX(0,Месяцы!Z62))<1E-6"),
    ("ЧП = ПДН − налог (каждый месяц)", "=SUMPRODUCT(ABS(Месяцы!AC3:AC62-(Месяцы!Y3:Y62-Месяцы!AB3:AB62)))<1E-6"),
    ("Накопленная ЧП = сумма ЧП", "=ABS(SUM(Месяцы!AC3:AC62)-Месяцы!AD62)<1E-6"),
    ("Остатки неотрицательны", "=MIN(Месяцы!F3:F62)>=0"),
    ("Капитал = норма × доля риска × средний остаток",
     "=SUMPRODUCT(ABS(Месяцы!P3:P62-Вводные!B36*Месяцы!K3:K62*Месяцы!G3:G62))<1E-6"),
    ("Матрица сценариев совпадает с помесячным расчётом", f"=SUMPRODUCT(ABS({SCEN_PBT}-Годы!B19:F19))<1E-6"),
    ("Режим 2 не даёт цену выше потолка",
     '=SUMPRODUCT((Юнит!B6:I6="потолок")*(Юнит!B8:I8>Вводные!B48+Вводные!B49+1E-9))=0'),
    ("Эффективная ставка = D/(F−D) × 365/t", "=ABS(Юнит!B8-Юнит!B9/Юнит!B10*365/Юнит!B4)<1E-9"),
    ("Компоненты счёта в сумме = D", "=ABS(Юнит!B11+Юнит!B12+Юнит!B13+Юнит!B14-Юнит!B9)<1E-9"),
    ("База чувствительности ≈ ПДН Г5", "=ABS(Чувствит!AJ43-Годы!F19)<1E-6"),
    ("Стресс: потери = ячейка сетки (доля и LGD из «Вводных»)",
     "=IFERROR(ABS(Стресс!B13-INDEX(Стресс!B27:E31,MATCH(Вводные!B77,Стресс!A27:A31,0),"
     "MATCH(Вводные!B42,Стресс!B26:E26,0)))<1E-9,TRUE)"),
]


def build(out: Path) -> Path:
    wb = openpyxl.load_workbook(SRC)
    wb["Годы"]["B42"] = PAYBACK
    f3 = wb["Месяцы"]["F3"].value
    assert "#REF!" in f3, f3
    wb["Месяцы"]["F3"] = f3.replace("Ставки!$B$10*#REF!", "Ставки!$B$10*0")
    # «Сводка»!A33:A40: метка выбранного сценария ссылалась на удалённую колонку; строка k ↔ (сценарий−1)×2 + режим
    sv = wb["Сводка"]
    for k in range(1, 9):
        cell = sv[f"A{32 + k}"]
        assert "#REF!" in cell.value, cell.value
        cell.value = (f'=LEFT(Сценарии!$A${2 + k},FIND(" (",Сценарии!$A${2 + k}&" (")-1)&" · "&Сценарии!$B${2 + k}'
                      f'&IF((Вводные!$B$33-1)*2+Вводные!$B$47={k}," ◄ выбран","")')
    ws = wb.create_sheet("Проверки")
    ws["A1"] = "Контрольные тождества модели (как engine/finmodel.py::checks)"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"], ws["B2"], ws["C2"] = "№", "Проверка", "Выполняется"
    for c in ("A2", "B2", "C2"):
        ws[c].font = Font(bold=True)
    for i, (name, formula) in enumerate(CHECKS, 1):
        r = 2 + i
        ws[f"A{r}"], ws[f"B{r}"], ws[f"C{r}"] = i, name, formula
    last = 2 + len(CHECKS)
    ws[f"B{last + 2}"] = "Все проверки"
    ws[f"C{last + 2}"] = f'=IF(COUNTIF(C3:C{last},TRUE)={len(CHECKS)},"ОК","ОШИБКА")'
    ws[f"B{last + 2}"].font = ws[f"C{last + 2}"].font = Font(bold=True)
    ws[f"C{last + 2}"].fill = PatternFill("solid", fgColor="E6F4EC")
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 62
    ws.column_dimensions["C"].width = 14
    wb.calculation.fullCalcOnLoad = True
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        if p := shutil.which(name):
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",):
        if Path(p).exists():
            return p
    return None


def recalc_and_check(book: Path) -> list[str]:
    """Пересчёт в LibreOffice; возвращает список ячеек с ошибками и итог листа «Проверки»."""
    exe = soffice()
    if not exe:
        raise RuntimeError("LibreOffice не найден: пересчёт невозможен")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([exe, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", tmp, str(book)],
                       check=True, capture_output=True, timeout=300)
        out = Path(tmp) / book.name
        shutil.copyfile(out, book)
    wb = openpyxl.load_workbook(book, data_only=True)
    bad = [f"{ws.title}!{c.coordinate}={c.value}" for ws in wb for row in ws.iter_rows() for c in row
           if isinstance(c.value, str) and c.value.startswith("#")]
    ws = wb["Проверки"]
    total = ws.cell(ws.max_row, 3).value
    if total != "ОК":
        bad.append(f"Проверки: итог {total!r}; ложные: "
                   + ", ".join(str(ws.cell(r, 2).value) for r in range(3, 3 + len(CHECKS))
                               if ws.cell(r, 3).value is not True))
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--recalc", action="store_true")
    a = ap.parse_args()
    out = build(Path(a.out))
    print(f"{out}: {len(CHECKS)} проверок, #REF! исправлены")
    if a.recalc:
        bad = recalc_and_check(out)
        print("Ошибок нет, все проверки ОК" if not bad else "\n".join(bad))
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
