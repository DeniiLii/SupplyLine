"""Реестр требований: защита от двойного финансирования.

Ключ требования — SHA-256 от нормализованных (anchor_id, supplier_id, upd_no, upd_date, amount_kopecks).
Уникальность обеспечивает уникальный индекс в БД; здесь чистая логика.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


def normalize_upd_no(upd_no: str) -> str:
    s = upd_no.strip().upper().replace("№", "")
    s = re.sub(r"[\s\-_/\\.]+", "", s)
    return s.lstrip("0") or "0"


def amount_kopecks(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).to_integral_value())


def claim_key(anchor_id: int, supplier_id: int, upd_no: str, upd_date: date, amount: Decimal) -> str:
    raw = "|".join([
        str(int(anchor_id)), str(int(supplier_id)), normalize_upd_no(upd_no),
        upd_date.isoformat(), str(amount_kopecks(amount)),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ClaimView:
    invoice_id: int
    anchor_id: int
    supplier_id: int
    upd_no: str
    upd_date: date
    amount: Decimal


def is_similar(a: ClaimView, b: ClaimView) -> bool:
    """«Похожий» счёт: тот же якорь и поставщик, сумма в пределах 1%, дата в пределах 3 дней."""
    if a.anchor_id != b.anchor_id or a.supplier_id != b.supplier_id:
        return False
    big = max(abs(a.amount), abs(b.amount))
    if big == 0 or abs(a.amount - b.amount) / big > Decimal("0.01"):
        return False
    return abs((a.upd_date - b.upd_date).days) <= 3


def find_similar(candidate: ClaimView, existing: list[ClaimView]) -> list[ClaimView]:
    return [e for e in existing if e.invoice_id != candidate.invoice_id and is_similar(candidate, e)]


class DuplicateClaim(Exception):
    def __init__(self, key: str, existing_invoice_id: int | None):
        self.key = key
        self.existing_invoice_id = existing_invoice_id
        super().__init__(
            "Требование уже есть в реестре"
            + (f" (счёт #{existing_invoice_id})" if existing_invoice_id else "")
            + ": повторное финансирование заблокировано"
        )
