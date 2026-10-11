"""Правиловый скоринг (без ML). Рейтинг якоря A–D задаёт PD и цену;
скоринг поставщика влияет только на лимит."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from engine.pricing import RATING_PD

D = Decimal


@dataclass(frozen=True)
class AnchorMetrics:
    debt_to_ebitda: Decimal  # долговая нагрузка, x
    avg_payment_delay_days: int  # средняя просрочка оплаты поставщикам, дней
    rejected_acceptance_share: Decimal  # доля отклонённых акцептов
    business_age_years: int


@dataclass
class ScoreResult:
    points: int
    rating: str
    pd: Decimal
    rules: list[dict] = field(default_factory=list)


# Таблица баллов: (метрика, порог, условие, баллы, текст правила)
ANCHOR_RULES = [
    ("debt_to_ebitda", D("1.5"), "le", 30, "Долговая нагрузка не выше 1,5× EBITDA"),
    ("debt_to_ebitda", D("3.0"), "le", 15, "Долговая нагрузка до 3,0× EBITDA"),
    ("avg_payment_delay_days", 3, "le", 30, "Платит поставщикам в срок (просрочка до 3 дней)"),
    ("avg_payment_delay_days", 10, "le", 15, "Средняя просрочка оплаты до 10 дней"),
    ("rejected_acceptance_share", D("0.02"), "le", 20, "Отклоняет не больше 2% счетов"),
    ("rejected_acceptance_share", D("0.05"), "le", 10, "Отклоняет не больше 5% счетов"),
    ("business_age_years", 10, "ge", 20, "Работает 10 лет и дольше"),
    ("business_age_years", 5, "ge", 10, "Работает от 5 лет"),
]
RATING_BANDS = [(80, "A"), (55, "B"), (35, "C"), (0, "D")]


def score_anchor(m: AnchorMetrics) -> ScoreResult:
    """Для каждой метрики срабатывает первое (самое строгое) выполненное правило."""
    points = 0
    fired: list[dict] = []
    seen: set[str] = set()
    for metric, thr, op, pts, text in ANCHOR_RULES:
        if metric in seen:
            continue
        val = getattr(m, metric)
        ok = val <= thr if op == "le" else val >= thr
        if ok:
            seen.add(metric)
            points += pts
            fired.append({"metric": metric, "value": str(val), "points": pts, "rule": text})
    for metric in ("debt_to_ebitda", "avg_payment_delay_days", "rejected_acceptance_share",
                   "business_age_years"):
        if metric not in seen:
            fired.append({"metric": metric, "value": str(getattr(m, metric)), "points": 0,
                          "rule": _miss_text(metric)})
    rating = next(r for floor, r in RATING_BANDS if points >= floor)
    return ScoreResult(points=points, rating=rating, pd=RATING_PD[rating], rules=fired)


def _miss_text(metric: str) -> str:
    return {
        "debt_to_ebitda": "Долговая нагрузка выше 3,0× EBITDA: 0 баллов",
        "avg_payment_delay_days": "Средняя просрочка оплаты больше 10 дней: 0 баллов",
        "rejected_acceptance_share": "Отклоняет больше 5% счетов: 0 баллов",
        "business_age_years": "Работает меньше 5 лет: 0 баллов",
    }[metric]


@dataclass(frozen=True)
class SupplierMetrics:
    revenue_mln: Decimal
    turnover_with_anchor_90d: Decimal  # ₽
    months_with_anchor: int
    returns_share: Decimal  # доля возвратов/корректировок УПД


def supplier_limit_share(m: SupplierMetrics) -> tuple[Decimal, list[dict]]:
    """Доля оборота с якорем за 90 дней, доступная как лимит поставщика."""
    share = D("0.7")
    rules = [{"rule": "Базовый лимит: 70% оборота с якорем за 90 дней", "effect": "0,70"}]
    if m.months_with_anchor >= 24:
        share += D("0.2")
        rules.append({"rule": "Работает с якорем 2 года и дольше", "effect": "+0,20"})
    elif m.months_with_anchor < 6:
        share -= D("0.2")
        rules.append({"rule": "Работает с якорем меньше 6 месяцев", "effect": "−0,20"})
    if m.returns_share > D("0.05"):
        share -= D("0.1")
        rules.append({"rule": "Возвраты и корректировки УПД больше 5%", "effect": "−0,10"})
    return max(D("0.3"), share), rules
