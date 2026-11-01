"""Цена одного счёта (раздел 2.1). Все деньги в Decimal, база ACT/365.

k = t/365
r_EL    = PD × LGD × (1 − cover)
r_total = r_fund + r_EL + r_opex + r_margin
D       = F × r_total × k
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

D = Decimal
KOP = D("0.01")
DAYS = D(365)

# Источники фондирования: премия к KС (раздел 2.2) и признак «на балансе»
FUNDING_SOURCES: dict[str, dict] = {
    "bank": {"name": "Банк-партнёр", "premium": D("0.010"), "range": (D("0.005"), D("0.010")),
             "on_balance": True, "badge": "Гипотеза"},
    "line": {"name": "Кредитная линия фактору", "premium": D("0.025"), "range": (D("0.02"), D("0.03")),
             "on_balance": True, "badge": "Гипотеза"},
    "cfa": {"name": "ЦФА для инвесторов", "premium": D("0.045"), "range": (D("0.03"), D("0.05")),
            "on_balance": False, "badge": "Факт и гипотеза"},
    "treasury": {"name": "Казначейства корпораций", "premium": D("0.020"), "range": (D("0.01"), D("0.03")),
                 "on_balance": False, "badge": "Гипотеза"},
    "syndication": {"name": "Синдикация", "premium": D("0.010"), "range": (D("0.005"), D("0.02")),
                    "on_balance": False, "badge": "Гипотеза"},
}
RATING_PD = {"A": D("0.005"), "B": D("0.010"), "C": D("0.020"), "D": D("0.040")}

KEY_RATE = D("0.14")
MSP_RATE = D("0.18")
SPEED_PREMIUM = D("0.01")
FACTORING_RANGE = (D("0.02"), D("0.07"))  # KС + 2…7%, вебинар крупного ритейлера, ноябрь 2023 (docs/FACTS_TODO.md)


def q(x: Decimal) -> Decimal:
    return x.quantize(KOP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceInput:
    face: Decimal  # F, ₽
    t_days: int
    r_fund: Decimal
    pd: Decimal
    lgd: Decimal = D("0.6")
    cover: Decimal = D(0)
    r_opex: Decimal = D("0.012")
    r_margin: Decimal = D("0.024")
    mode: int = 1  # 1 по формуле, 2 с потолком рынка
    msp_rate: Decimal = MSP_RATE
    speed_premium: Decimal = SPEED_PREMIUM

    def __post_init__(self) -> None:
        if self.face <= 0:
            raise ValueError("Номинал счёта должен быть больше нуля")
        if self.t_days <= 0:
            raise ValueError("Срок финансирования должен быть больше нуля")
        for name in ("r_fund", "pd", "lgd", "cover", "r_opex"):
            if getattr(self, name) < 0:
                raise ValueError(f"Параметр {name} не может быть отрицательным")
        for name in ("pd", "lgd", "cover"):
            if getattr(self, name) > 1:
                raise ValueError(f"Параметр {name} должен быть не больше 100%")
        if self.mode not in (1, 2):
            raise ValueError("Режим цены должен быть 1 или 2")


@dataclass(frozen=True)
class Price:
    k: Decimal
    r_el: Decimal
    r_total_formula: Decimal
    r_cap: Decimal
    r_total: Decimal
    capped: bool
    r_margin_effective: Decimal
    discount: Decimal
    payout: Decimal
    comp_funding: Decimal
    comp_loss: Decimal
    comp_opex: Decimal
    comp_margin: Decimal
    spread: Decimal
    spread_pct_cycle: Decimal
    eff_rate: Decimal
    msp_rate: Decimal
    cap_rate: Decimal
    cheaper_than_msp: bool

    def as_dict(self) -> dict:
        return asdict(self)


def cap_discount_rate(msp_rate: Decimal, speed_premium: Decimal, t_days: int) -> Decimal:
    """Потолок рынка в терминах ставки дисконта: e / (1 + e·t/365), e = МСП + премия за скорость."""
    e = msp_rate + speed_premium
    return e / (1 + e * D(t_days) / DAYS)


def price(inp: PriceInput) -> Price:
    F = D(inp.face)
    k = D(inp.t_days) / DAYS
    r_el = inp.pd * inp.lgd * (1 - inp.cover)
    r_formula = inp.r_fund + r_el + inp.r_opex + inp.r_margin
    r_cap = cap_discount_rate(inp.msp_rate, inp.speed_premium, inp.t_days)
    if inp.mode == 2 and r_formula > r_cap:
        r_total, capped = r_cap, True
    else:
        r_total, capped = r_formula, False
    r_margin_eff = r_total - inp.r_fund - r_el - inp.r_opex

    disc = q(F * r_total * k)
    c_fund = q(F * inp.r_fund * k)
    c_loss = q(F * r_el * k)
    c_opex = q(F * inp.r_opex * k)
    c_margin = disc - c_fund - c_loss - c_opex  # остаток округления относится к марже
    spread = q(F * (r_total - inp.r_fund) * k)
    payout = F - disc
    eff = (disc / payout) * DAYS / D(inp.t_days)
    return Price(
        k=k, r_el=r_el, r_total_formula=r_formula, r_cap=r_cap, r_total=r_total, capped=capped,
        r_margin_effective=r_margin_eff, discount=disc, payout=payout, comp_funding=c_fund,
        comp_loss=c_loss, comp_opex=c_opex, comp_margin=c_margin, spread=spread,
        spread_pct_cycle=spread / F, eff_rate=eff, msp_rate=inp.msp_rate,
        cap_rate=inp.msp_rate + inp.speed_premium, cheaper_than_msp=eff <= inp.msp_rate,
    )


def r_fund_for(source: str, key_rate: Decimal = KEY_RATE) -> Decimal:
    return key_rate + FUNDING_SOURCES[source]["premium"]


def r_fund_blended(weights: dict[str, Decimal], key_rate: Decimal = KEY_RATE,
                   premiums: dict[str, Decimal] | None = None) -> Decimal:
    total = sum(weights.values(), D(0))
    if abs(total - 1) > D("1e-9"):
        raise ValueError("Веса источников фондирования должны давать 100%")
    prem = premiums or {k: v["premium"] for k, v in FUNDING_SOURCES.items()}
    return sum((w * (key_rate + prem[s]) for s, w in weights.items()), D(0))


def max_premium_for_msp_parity(key_rate: Decimal, pd: Decimal, lgd: Decimal, cover: Decimal,
                               r_opex: Decimal, r_margin: Decimal, t_days: int,
                               msp_rate: Decimal = MSP_RATE) -> Decimal:
    """Премия фондирования к KС, при которой эффективная ставка поставщика = кредит МСП."""
    r_max = msp_rate / (1 + msp_rate * D(t_days) / DAYS)
    return r_max - key_rate - pd * lgd * (1 - cover) - r_opex - r_margin


def premium_curve(key_rate: Decimal, pd: Decimal, lgd: Decimal, cover: Decimal, r_opex: Decimal,
                  r_margin: Decimal, t_days: int, step_bp: int = 25, max_bp: int = 600) -> list[dict]:
    """Эффективная ставка поставщика в зависимости от премии фондирования (0…6 п.п.)."""
    out = []
    for bp in range(0, max_bp + 1, step_bp):
        prem = D(bp) / D(10000)
        p = price(PriceInput(face=D(1_000_000), t_days=t_days, r_fund=key_rate + prem, pd=pd,
                             lgd=lgd, cover=cover, r_opex=r_opex, r_margin=r_margin))
        out.append({"premium": prem, "eff_rate": p.eff_rate, "r_total": p.r_total})
    return out


def stationary_scale(turnover: Decimal, t_days: int, on_balance_share: Decimal,
                     cap_norm: Decimal, borne: Decimal, r_total: Decimal, r_fund: Decimal) -> dict:
    """Стационарная оценка порядка величин (только для проверки)."""
    avg = turnover * D(t_days) / DAYS
    return {
        "avg_balance": avg,
        "on_balance": avg * on_balance_share,
        "capital": cap_norm * borne * avg,
        "spread": turnover * (r_total - r_fund) * D(t_days) / DAYS,
    }
