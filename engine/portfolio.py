"""Лимиты и концентрация для операционного демо; агрегаты портфеля.

Потолки концентрации считаются от базы max(текущий портфель после сделки, плановый размер программы),
иначе первый же счёт давал бы 100% концентрации (см. docs/DECISIONS.md).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

D = Decimal

# По умолчанию 15%: ниже безопасной доли стресс-теста финмодели (16,35%), см. DECISIONS 28.
# Платформа хранит текущее значение в настройке anchor_cap (0,05–0,25).
ANCHOR_CAP = D("0.15")
INDUSTRY_CAP = D("0.40")
# ₽ 2,5 млрд — плановый портфель фазы 0 (Гипотеза). При потолке 15% даёт тот же предел на якоря в рублях
# (375 млн ₽), что прежние 1,5 млрд при 25%: см. DECISIONS 29
PROGRAM_SIZE = D("2500000000")


@dataclass(frozen=True)
class Exposure:
    anchor_id: int
    supplier_id: int
    industry: str
    amount: Decimal  # ₽, непогашенный номинал


@dataclass(frozen=True)
class LimitCheck:
    rule: str
    ok: bool
    used: Decimal
    limit: Decimal
    detail: str

    def as_dict(self) -> dict:
        return {"rule": self.rule, "ok": self.ok, "used": self.used, "limit": self.limit,
                "detail": self.detail}


def pct(x: Decimal) -> str:
    """0,15 → «15%», 0,125 → «12,5%»."""
    v = (x * 100).normalize()
    return f"{v:f}".replace(".", ",") + "%"


def supplier_limit(share: Decimal, turnover_90d: Decimal, anchor_sublimit: Decimal) -> Decimal:
    return min(share * turnover_90d, anchor_sublimit)


def check_limits(
    *, new: Exposure, book: list[Exposure], anchor_limit: Decimal, supplier_limit_value: Decimal,
    program_size: Decimal = PROGRAM_SIZE, anchor_cap: Decimal = ANCHOR_CAP,
    industry_cap: Decimal = INDUSTRY_CAP,
) -> list[LimitCheck]:
    by_anchor = sum((e.amount for e in book if e.anchor_id == new.anchor_id), D(0))
    by_supplier = sum((e.amount for e in book
                       if e.supplier_id == new.supplier_id and e.anchor_id == new.anchor_id), D(0))
    by_industry = sum((e.amount for e in book if e.industry == new.industry), D(0))
    total_after = sum((e.amount for e in book), D(0)) + new.amount
    base = max(total_after, program_size)
    out = [
        LimitCheck("Лимит якоря", by_anchor + new.amount <= anchor_limit,
                   by_anchor + new.amount, anchor_limit,
                   "Сумма непогашенных счетов якоря с учётом нового не превышает его лимит"),
        LimitCheck("Лимит поставщика", by_supplier + new.amount <= supplier_limit_value,
                   by_supplier + new.amount, supplier_limit_value,
                   "Лимит = min(доля × оборот с якорем за 90 дней, суб-лимит якоря)"),
        LimitCheck(f"Концентрация на одного якоря: не больше {pct(anchor_cap)}",
                   (by_anchor + new.amount) <= anchor_cap * base,
                   by_anchor + new.amount, anchor_cap * base,
                   "Доля якоря в портфеле (база — больше из портфеля и плана программы)"),
        LimitCheck(f"Концентрация на отрасль: не больше {pct(industry_cap)}",
                   (by_industry + new.amount) <= industry_cap * base,
                   by_industry + new.amount, industry_cap * base,
                   "Доля отрасли в портфеле"),
    ]
    return out


def first_failed(checks: list[LimitCheck]) -> LimitCheck | None:
    return next((c for c in checks if not c.ok), None)


def concentration(book: list[Exposure]) -> dict[int, Decimal]:
    total = sum((e.amount for e in book), D(0))
    agg: dict[int, Decimal] = defaultdict(lambda: D(0))
    for e in book:
        agg[e.anchor_id] += e.amount
    return {k: (v / total if total else D(0)) for k, v in agg.items()}
