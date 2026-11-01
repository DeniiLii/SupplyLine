"""Книга v2 для аналитики (WP8): нет #REF!, лист «Проверки»; с LibreOffice — пересчёт без ошибок и паритет с движком."""

import os

import openpyxl
import pytest

from engine.finmodel import FinParams
from scripts.build_model_v2 import CHECKS, build, recalc_and_check, soffice
from tests.test_excel_parity import compare_book


def test_v2_formulas(tmp_path):
    book = build(tmp_path / "v2.xlsx")
    wb = openpyxl.load_workbook(book)
    refs = [f"{ws.title}!{c.coordinate}" for ws in wb for row in ws.iter_rows() for c in row
            if isinstance(c.value, str) and "#REF!" in c.value]
    assert refs == []
    assert len(CHECKS) == 19
    assert "Проверки" in wb.sheetnames and wb["Проверки"].max_row >= 2 + len(CHECKS)


def test_v2_recalc_parity(tmp_path):
    if soffice() is None:
        if os.environ.get("CI"):
            pytest.fail("В CI нужен LibreOffice для пересчёта книги v2")
        pytest.skip("LibreOffice не установлен: пересчёт книги v2 пропущен (в CI обязателен)")
    book = build(tmp_path / "v2.xlsx")
    assert recalc_and_check(book) == []
    compare_book(book, FinParams()).assert_ok()
