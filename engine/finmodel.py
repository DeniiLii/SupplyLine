"""Финансовая модель SupplyLine на 60 месяцев.

Единственный источник правды для экрана «Портфельная модель». Воспроизводит книгу
docs/model/SupplyLine_financial_model.xlsx (листы Расходы, Рост, Ставки, Юнит, Месяцы,
Годы, Сценарии, Чувствит, Стресс). Соответствие ячеек описано в docs/model/MAPPING.md.

Соглашения: деньги в ₽ млн, ставки — доли, ACT/365, месяц = 365/12 дня.
Все вычисления в Decimal; в API значения отдаются как float.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from decimal import Decimal, getcontext
from typing import Any

getcontext().prec = 34

D = Decimal
ZERO = D(0)
ONE = D(1)
DAYS = D(365)
MONTH_DAYS = DAYS / 12
MONTHS = 60
YEARS = 5

SCENARIOS = ("A", "B", "C", "M")
SCENARIO_NAMES = {
    "A": "Банк-партнёр (100% баланс)",
    "B": "Кредитная линия фактору (100%)",
    "C": "ЦФА для инвесторов (100%)",
    "M": "Смешанная структура",
}
SOURCES = ("bal", "line", "cfa", "tre", "syn")
SOURCE_NAMES = {
    "bal": "Баланс организатора (банк-партнёр)",
    "line": "Кредитная линия небанковскому фактору",
    "cfa": "ЦФА для квалифицированных инвесторов",
    "tre": "Казначейства корпораций",
    "syn": "Синдикация",
}
PRICE_MODES = (1, 2)
PRICE_MODE_NAMES = {1: "по формуле", 2: "с потолком рынка"}


def d(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return D(repr(x))
    return D(x)


def _vec(*xs: Any) -> tuple[Decimal, ...]:
    return tuple(d(x) for x in xs)


@dataclass(frozen=True)
class FinParams:
    """Вводные модели. Значения по умолчанию = лист «Вводные» книги-эталона."""

    # Макро
    ks_now: Decimal = D("0.14")
    ks_scenario: int = 1  # 1 константа, 2 смягчение, 3 шок
    ks_pass_through: int = 1  # 1 перенос KС в цену, 2 цена по KС старта
    ks_paths: tuple[tuple[Decimal, ...], ...] = (
        _vec("0.14", "0.14", "0.14", "0.14", "0.14"),
        _vec("0.115", "0.1", "0.09", "0.085", "0.085"),
        _vec("0.17", "0.17", "0.17", "0.17", "0.17"),
    )
    # Источники фондирования: премия к KС и признак «на балансе»
    premiums: tuple[Decimal, ...] = _vec("0.01", "0.025", "0.045", "0.02", "0.01")
    on_balance: tuple[int, ...] = (1, 1, 0, 0, 0)
    # Целевые веса источников по сценариям A, B, C, M (порядок SOURCES)
    weights: tuple[tuple[Decimal, ...], ...] = (
        _vec(1, 0, 0, 0, 0),
        _vec(0, 1, 0, 0, 0),
        _vec(0, 0, 1, 0, 0),
        _vec("0.6", 0, "0.25", "0.1", "0.05"),
    )
    ramp_flags: tuple[int, ...] = (0, 0, 0, 1)
    ramp: tuple[Decimal, ...] = _vec(0, "0.8", 1, 1, 1)
    # Выбор сценария, риск и капитал
    scenario: str = "M"
    retention: Decimal = D("0.1")
    cfa_fee: Decimal = D("0.0005")
    cap_norm: Decimal = D("0.1")
    eq_switch: int = 1
    coe: Decimal = D("0.2")
    tax: Decimal = D("0.25")
    # Цена и риск
    t_days: Decimal = D(45)
    lgd: Decimal = D("0.6")
    cover: Decimal = D(0)
    ins_rate: Decimal = D("0.01")
    r_opex: Decimal = D("0.012")
    r_margin: Decimal = D("0.024")
    price_mode: int = 1
    msp_rate: Decimal = D("0.18")
    speed_prem: Decimal = D("0.01")
    loss_mult: Decimal = D(1)
    # Рейтинги якорей: доли и PD (A, B, C, D)
    rating_shares: tuple[Decimal, ...] = _vec("0.4", "0.45", "0.125", "0.025")
    rating_pd: tuple[Decimal, ...] = _vec("0.005", "0.01", "0.02", "0.04")
    # Объёмы
    turnover_bn: tuple[Decimal, ...] = _vec(8, 22, 50, 90, 150)
    suppliers: tuple[int, ...] = (40, 250, 700, 1500, 2500)
    anchors: tuple[int, ...] = (5, 12, 25, 40, 55)
    avg_invoice: Decimal = D(5)
    var_pct: Decimal = D("0.0003")
    # Постоянные расходы
    fte: tuple[Decimal, ...] = _vec(20, 30, 40, 45, 50)
    it: tuple[Decimal, ...] = _vec(60, 70, 80, 90, 100)
    comp: tuple[Decimal, ...] = _vec(25, 30, 35, 40, 45)
    mkt: tuple[Decimal, ...] = _vec(25, 35, 45, 55, 60)
    fte_cost: Decimal = D("0.5")
    fte_idx: Decimal = D("0.07")
    ga: Decimal = D("0.1")
    # Рынок
    market_mid_companies: int = 24400
    market_factoring_turnover_bn: Decimal = D(10252)
    market_factoring_portfolio_bn: Decimal = D(2790)
    # Стресс
    stress_share: Decimal = D("0.25")
    stress_month: int = 42

    def with_overrides(self, **kw: Any) -> FinParams:
        clean: dict[str, Any] = {}
        types = {f.name: f.type for f in fields(self)}
        for k, v in kw.items():
            if k not in types:
                raise ValueError(f"Неизвестный параметр модели: {k}")
            clean[k] = _coerce(getattr(self, k), v)
        return replace(self, **clean)


def _coerce(proto: Any, v: Any) -> Any:
    if isinstance(proto, tuple):
        return tuple(_coerce(proto[0] if proto else D(0), x) for x in v)
    if isinstance(proto, bool):
        return bool(v)
    if isinstance(proto, int):
        return int(v)
    if isinstance(proto, Decimal):
        return d(v)
    return v


class FinModelError(ValueError):
    """Недопустимые вводные (например, траектория оборота уходит в минус)."""


# ---------------------------------------------------------------- базовые величины


def pd_port(p: FinParams) -> Decimal:
    return sum((s * q for s, q in zip(p.rating_shares, p.rating_pd)), ZERO)


def el_rate(p: FinParams) -> Decimal:
    return pd_port(p) * p.lgd * (ONE - p.cover)


def r_el(p: FinParams) -> Decimal:
    return el_rate(p) + p.cover * p.ins_rate


def cap_credit(p: FinParams) -> Decimal:
    """Потолок в терминах кредита: ставка МСП + премия за скорость."""
    return p.msp_rate + p.speed_prem


# Допуск границы классификации: в режиме «с потолком» eff равна потолку алгебраически,
# но Decimal даёт расхождение ~1e-34 в любую сторону (Excel сравнивает двоичные числа и попадает в «равно»)
EPS = D("1e-12")


def price_position(p: FinParams, eff: Decimal) -> str:
    if eff <= p.msp_rate + EPS:
        return "дешевле кредита МСП"
    if eff <= cap_credit(p) + EPS:
        return "дороже кредита, в пределах премии"
    return "выше потолка рынка"


def cap_discount(p: FinParams, t: Decimal | None = None, e: Decimal | None = None) -> Decimal:
    t = p.t_days if t is None else t
    e = cap_credit(p) if e is None else e
    return e / (ONE + e * t / DAYS)


def eff_rate(r: Decimal, t: Decimal) -> Decimal:
    return r / (ONE - r * t / DAYS)


def balance_coefs(p: FinParams) -> tuple[Decimal, Decimal, Decimal]:
    def c(j: int) -> Decimal:
        return min(ONE, max(ZERO, (p.t_days - j * MONTH_DAYS) / MONTH_DAYS))

    return c(0), c(1), c(2)


def fixed_opex(p: FinParams) -> list[Decimal]:
    out = []
    for y in range(YEARS):
        cost = p.fte_cost * (ONE + p.fte_idx) ** y
        staff = p.fte[y] * cost * 12
        out.append((staff + p.it[y] + p.comp[y] + p.mkt[y]) * (ONE + p.ga))
    return out


def fixed_opex_breakdown(p: FinParams) -> list[dict[str, Decimal]]:
    rows = []
    for y in range(YEARS):
        cost = p.fte_cost * (ONE + p.fte_idx) ** y
        staff = p.fte[y] * cost * 12
        sub = staff + p.it[y] + p.comp[y] + p.mkt[y]
        rows.append(
            {
                "fte": p.fte[y],
                "fte_cost": cost,
                "staff": staff,
                "it": p.it[y],
                "comp": p.comp[y],
                "mkt": p.mkt[y],
                "subtotal": sub,
                "ga": sub * p.ga,
                "total": sub * (ONE + p.ga),
            }
        )
    return rows


def ks_path(p: FinParams) -> tuple[Decimal, ...]:
    if p.ks_scenario not in (1, 2, 3):
        raise FinModelError("Сценарий KС должен быть 1, 2 или 3")
    return p.ks_paths[p.ks_scenario - 1]


# ---------------------------------------------------------------- ставки


@dataclass(frozen=True)
class Rates:
    scenario: str
    year: int
    ramp: Decimal
    w: dict[str, Decimal]
    w_on: Decimal
    w_cfa: Decimal
    prem_mix: Decimal
    prem_on: Decimal
    ks: Decimal
    r_fund: Decimal
    borne: Decimal
    r_fund_price: Decimal
    r_cp: Decimal
    r_cap: Decimal
    r_el: Decimal
    el_rate: Decimal

    def r_app(self, mode: int) -> Decimal:
        return self.r_cp if mode == 1 else self.r_cap

    def margin(self, mode: int, p: FinParams) -> Decimal:
        return self.r_app(mode) - self.r_fund - self.r_el - p.r_opex


def rates(p: FinParams, scenario: str, year: int) -> Rates:
    """Лист «Ставки», блок сценария, столбец года (year = 1..5)."""
    si = SCENARIOS.index(scenario)
    tw = p.weights[si]
    ramp = p.ramp[year - 1] if p.ramp_flags[si] == 1 else ONE
    w = {
        "bal": tw[0] + (ONE - ramp) * (tw[2] + tw[3] + tw[4]),
        "line": tw[1],
        "cfa": tw[2] * ramp,
        "tre": tw[3] * ramp,
        "syn": tw[4] * ramp,
    }
    ws = [w[k] for k in SOURCES]
    w_on = sum((wi * oi for wi, oi in zip(ws, p.on_balance)), ZERO)
    prem_mix = sum((wi * pi for wi, pi in zip(ws, p.premiums)), ZERO)
    if w_on > 0:
        prem_on = (
            sum((wi * pi * oi for wi, pi, oi in zip(ws, p.premiums, p.on_balance)), ZERO) / w_on
        )
    else:
        prem_on = p.premiums[0]
    ks = ks_path(p)[year - 1]
    r_fund = ks + prem_mix
    borne = w_on + (ONE - w_on) * p.retention
    r_fund_price = r_fund if p.ks_pass_through == 1 else p.ks_now + prem_mix
    rel = r_el(p)
    r_cp = r_fund_price + rel + p.r_opex + p.r_margin
    r_cap = min(r_cp, cap_discount(p))
    return Rates(
        scenario, year, ramp, w, w_on, w["cfa"], prem_mix, prem_on, ks, r_fund, borne,
        r_fund_price, r_cp, r_cap, rel, el_rate(p),
    )


def weights_sum(p: FinParams, scenario: str, year: int) -> Decimal:
    return sum(rates(p, scenario, year).w.values(), ZERO)


# ---------------------------------------------------------------- траектория


def nodes(p: FinParams) -> list[Decimal]:
    """Лист «Рост»: узлы v0..v5 месячного оборота."""
    v = [ZERO]
    for y in range(YEARS):
        ty = p.turnover_bn[y] * 1000
        v.append((ty - D("5.5") * v[-1]) / D("6.5"))
    if min(v) < 0:
        raise FinModelError(
            "Траектория оборота уходит в минус: оборот года слишком мал относительно предыдущего"
        )
    return v


def trajectory(p: FinParams) -> dict[str, list[Decimal]]:
    v = nodes(p)
    c0, c1, c2 = balance_coefs(p)
    T: list[Decimal] = []
    for m in range(1, MONTHS + 1):
        y = (m - 1) // 12 + 1
        k = m - 12 * (y - 1)
        T.append(v[y - 1] + (v[y] - v[y - 1]) * k / 12)
    bal: list[Decimal] = []
    avg: list[Decimal] = []
    for i in range(MONTHS):
        b = c0 * T[i] + (c1 * T[i - 1] if i >= 1 else ZERO) + (c2 * T[i - 2] if i >= 2 else ZERO)
        bal.append(b)
        avg.append((b + (bal[i - 1] if i >= 1 else ZERO)) / 2)
    return {"nodes": v, "turnover": T, "bal_end": bal, "avg": avg}


# ---------------------------------------------------------------- помесячный расчёт


MONTH_FIELDS = (
    "month", "year", "month_in_year", "turnover", "bal_end", "avg", "ks", "r_app", "r_fund",
    "borne", "w_cfa", "prem_on", "income", "fund_gross", "capital", "eq_benefit", "fund_net",
    "el_all", "el_borne", "ins", "cfa_fee", "var_opex", "fix_opex", "pbt", "cum_pbt",
    "tax_cum", "tax", "np", "cum_np", "eq_need",
)


def monthly(p: FinParams, scenario: str | None = None, mode: int | None = None) -> list[dict]:
    scenario = scenario or p.scenario
    mode = mode or p.price_mode
    tr = trajectory(p)
    fx = fixed_opex(p)
    rs = [rates(p, scenario, y) for y in range(1, YEARS + 1)]
    rows: list[dict] = []
    cum_pbt = cum_np = ZERO
    prev_tax_cum = ZERO
    for i in range(MONTHS):
        m = i + 1
        y = (m - 1) // 12 + 1
        r = rs[y - 1]
        avg = tr["avg"][i]
        T = tr["turnover"][i]
        r_app = r.r_app(mode)
        income = avg * r_app / 12
        fund_gross = avg * r.r_fund / 12
        capital = p.cap_norm * r.borne * avg
        eq_benefit = p.eq_switch * capital * (r.ks + r.prem_on) / 12
        fund_net = fund_gross - eq_benefit
        el_all = avg * r.el_rate / 12
        el_borne = el_all * r.borne * p.loss_mult
        ins = avg * p.cover * p.ins_rate / 12
        cfa_fee = T * r.w_cfa * p.cfa_fee
        var_opex = T * p.var_pct
        fix = fx[y - 1] / 12
        pbt = income - fund_net - el_borne - ins - cfa_fee - var_opex - fix
        cum_pbt += pbt
        tax_cum = p.tax * max(ZERO, cum_pbt)
        tax = tax_cum - prev_tax_cum
        prev_tax_cum = tax_cum
        np_ = pbt - tax
        cum_np += np_
        rows.append(
            dict(
                month=m, year=y, month_in_year=m - 12 * (y - 1), turnover=T,
                bal_end=tr["bal_end"][i], avg=avg, ks=r.ks, r_app=r_app, r_fund=r.r_fund,
                borne=r.borne, w_cfa=r.w_cfa, prem_on=r.prem_on, income=income,
                fund_gross=fund_gross, capital=capital, eq_benefit=eq_benefit,
                fund_net=fund_net, el_all=el_all, el_borne=el_borne, ins=ins,
                cfa_fee=cfa_fee, var_opex=var_opex, fix_opex=fix, pbt=pbt, cum_pbt=cum_pbt,
                tax_cum=tax_cum, tax=tax, np=np_, cum_np=cum_np, eq_need=capital - cum_np,
            )
        )
    return rows


# ---------------------------------------------------------------- годы и KPI


def _per_bal(p: FinParams, r: Rates, mode: int) -> Decimal:
    return (
        r.r_app(mode)
        - r.r_fund
        + p.eq_switch * p.cap_norm * r.borne * (r.ks + r.prem_on)
        - r.el_rate * r.borne * p.loss_mult
        - p.cover * p.ins_rate
    )


def _cm(p: FinParams, r: Rates, mode: int) -> Decimal:
    return (p.t_days / DAYS) * _per_bal(p, r, mode) - p.var_pct - r.w_cfa * p.cfa_fee


def breakeven(fix: Decimal, cm: Decimal) -> Decimal | None:
    return fix / cm if cm > 0 else None


def yearly(p: FinParams, months: list[dict], scenario: str, mode: int) -> list[dict]:
    fx = fixed_opex(p)
    out = []
    for y in range(1, YEARS + 1):
        ms = [r for r in months if r["year"] == y]
        s = {k: sum((r[k] for r in ms), ZERO) for k in (
            "turnover", "income", "fund_gross", "eq_benefit", "fund_net", "el_borne", "ins",
            "cfa_fee", "var_opex", "fix_opex", "pbt", "tax", "np",
        )}
        avg_bal = sum((r["avg"] for r in ms), ZERO) / 12
        cap_avg = sum((r["capital"] for r in ms), ZERO) / 12
        r = rates(p, scenario, y)
        nii = s["income"] - s["fund_net"]
        costs = s["var_opex"] + s["fix_opex"] + s["cfa_fee"]
        per_bal = _per_bal(p, r, mode)
        cm = _cm(p, r, mode)
        r_app = r.r_app(mode)
        out.append(
            dict(
                year=y,
                **s,
                turnover_bn=s["turnover"] / 1000,
                invoices=s["turnover"] / p.avg_invoice,
                avg_bal=avg_bal,
                bal_end=ms[-1]["bal_end"],
                avg_last=ms[-1]["avg"],
                nii=nii,
                cum_np=ms[-1]["cum_np"],
                capital_avg=cap_avg,
                rorc=s["np"] / cap_avg if cap_avg > 0 else ZERO,
                econ=s["np"] - p.coe * cap_avg,
                cost_to_nii=costs / nii if nii > 0 else ZERO,
                nim=nii / avg_bal if avg_bal > 0 else ZERO,
                opex_to_turnover=costs / s["turnover"],
                off_balance_share=ONE - r.w_on,
                r_app=r_app,
                eff=eff_rate(r_app, p.t_days),
                msp=p.msp_rate,
                eff_minus_msp=eff_rate(r_app, p.t_days) - p.msp_rate,
                margin=r.margin(mode, p),
                w_on=r.w_on,
                borne=r.borne,
                r_fund=r.r_fund,
                ks=r.ks,
                per_bal=per_bal,
                cm=cm,
                breakeven_turnover=breakeven(fx[y - 1], cm),
                suppliers=p.suppliers[y - 1],
                anchors=p.anchors[y - 1],
            )
        )
    return out


def kpis(p: FinParams, months: list[dict], years: list[dict]) -> dict:
    needs = [r["eq_need"] for r in months]
    peak = max(needs)
    peak_month = needs.index(peak) + 1
    pos = [r["month"] for r in months if r["np"] > 0]
    nonpos = [r["month"] for r in months if r["np"] <= 0]
    last_nonpos = max(nonpos) if nonpos else 0
    payback = next((r["month"] for r in months if r["cum_np"] > 0), None)
    cum = [r["cum_np"] for r in months]
    bottom = min(cum)
    be5 = years[4]["breakeven_turnover"]
    return dict(
        eq_need_peak=max(ZERO, peak),
        eq_need_peak_month=peak_month,
        first_positive_np_month=min(pos) if pos else None,
        sustained_positive_month=None if last_nonpos >= MONTHS else last_nonpos + 1,
        payback_month=payback,
        cum_np_bottom=bottom,
        cum_np_bottom_month=cum.index(bottom) + 1,
        cum_pbt_5y=months[-1]["cum_pbt"],
        cum_np_5y=months[-1]["cum_np"],
        tax_5y=sum((r["tax"] for r in months), ZERO),
        breakeven_turnover_y5=be5,
        breakeven_share_y5=(be5 / years[4]["turnover"]) if be5 is not None else None,
    )


# ---------------------------------------------------------------- матрица сценариев


def scenario_annual(p: FinParams, scenario: str, mode: int, tr: dict | None = None) -> dict:
    """Лист «Сценарии»: годовой расчёт на общей траектории оборота и остатков."""
    tr = tr or trajectory(p)
    fx = fixed_opex(p)
    years = []
    cum_pbt = cum_np = ZERO
    for y in range(1, YEARS + 1):
        r = rates(p, scenario, y)
        sl = slice(12 * (y - 1), 12 * y)
        avg_bal = sum(tr["avg"][sl], ZERO) / 12
        T = sum(tr["turnover"][sl], ZERO)
        r_app = r.r_app(mode)
        income = avg_bal * r_app
        fund_net = avg_bal * (r.r_fund - p.eq_switch * p.cap_norm * r.borne * (r.ks + r.prem_on))
        el_b = avg_bal * r.el_rate * r.borne * p.loss_mult
        ins = avg_bal * p.cover * p.ins_rate
        cfa = T * r.w_cfa * p.cfa_fee
        var = T * p.var_pct
        fix = fx[y - 1]
        pbt = income - fund_net - el_b - ins - cfa - var - fix
        prev = cum_pbt
        cum_pbt += pbt
        tax = p.tax * (max(ZERO, cum_pbt) - max(ZERO, prev))
        np_ = pbt - tax
        cum_np += np_
        capital_end = p.cap_norm * r.borne * tr["avg"][12 * y - 1]
        cm = _cm(p, r, mode)
        years.append(
            dict(
                year=y, r_app=r_app, income=income, fund_net=fund_net, el_borne=el_b, ins=ins,
                cfa_fee=cfa, var_opex=var, fix_opex=fix, pbt=pbt, cum_pbt=cum_pbt, tax=tax,
                np=np_, cum_np=cum_np, capital_end=capital_end, eq_need_end=capital_end - cum_np,
                eff=eff_rate(r_app, p.t_days), margin=r.margin(mode, p),
                per_bal=_per_bal(p, r, mode), cm=cm, breakeven_turnover=breakeven(fix, cm),
            )
        )
    y5 = years[-1]
    eq = max(ZERO, max(yr["eq_need_end"] for yr in years))
    if y5["np"] <= 0:
        verdict = "убыточно в Г5"
    elif y5["eff"] <= cap_credit(p):
        verdict = "прибыльно, цена ≤ потолка"
    else:
        verdict = "прибыльно, цена > потолка"
    return dict(
        scenario=scenario, mode=mode, years=years,
        pbt=[yr["pbt"] for yr in years], np5=y5["np"], cum_np5=y5["cum_np"], eff5=y5["eff"],
        eff_minus_msp5=y5["eff"] - p.msp_rate, margin5=y5["margin"],
        breakeven5=y5["breakeven_turnover"], eq_need=eq, verdict=verdict,
    )


def scenario_matrix(p: FinParams) -> list[dict]:
    tr = trajectory(p)
    return [scenario_annual(p, s, m, tr) for s in SCENARIOS for m in PRICE_MODES]


# ---------------------------------------------------------------- юнит-экономика


def unit_economics(p: FinParams, scenario: str, mode: int, year: int = 5,
                   F: Decimal | None = None) -> dict:
    """Лист «Юнит»: один счёт, деньги в ₽ тыс."""
    F = p.avg_invoice * 1000 if F is None else d(F)
    t = p.t_days
    r = rates(p, scenario, year)
    r_app = r.r_app(mode)
    k = t / DAYS
    Dsc = F * r_app * k
    recv = F - Dsc
    fund = F * r.r_fund * k
    el = F * r.r_el * k
    opex = F * p.r_opex * k
    margin = Dsc - fund - el - opex
    msp_cost = recv * p.msp_rate * k
    eff = eff_rate(r_app, t)
    position = price_position(p, eff)
    return dict(
        scenario=scenario, mode=mode, year=year, F=F, t=t, r=r_app, eff=eff, D=Dsc, recv=recv,
        fund=fund, el=el, opex=opex, margin=margin, margin_rate=r.margin(mode, p),
        margin_per_1000=margin / F * 1000, msp_cost=msp_cost, overpay=Dsc - msp_cost,
        position=position, r_fund=r.r_fund, r_el=r.r_el, r_opex=p.r_opex,
    )


# ---------------------------------------------------------------- чувствительность

SENS_DRIVERS: tuple[tuple[str, str, Decimal, Decimal, str], ...] = (
    ("dt", "Срок финансирования, дней", D(-15), D(15), "±15 дней; остаток пропорционален сроку (приближение)"),
    ("kT", "Оборот Г5", D("0.7"), D("1.3"), "−30% / +30%"),
    ("dlgd", "LGD (потери при дефолте)", D("-0.2"), D("0.2"), "±20 п.п."),
    ("kpd", "PD портфеля", D("0.5"), D(2), "×0,5 / ×2"),
    ("dks", "Ключевая ставка Г5", D("-0.03"), D("0.03"), "±3 п.п."),
    ("dprem", "Премия фондирования", D("-0.01"), D("0.01"), "±1 п.п."),
    ("dmargin", "Маржа платформы в цене", D("-0.01"), D("0.01"), "±1 п.п."),
    ("kfix", "Постоянные расходы Г5", D("0.8"), D("1.2"), "−20% / +20%"),
    ("dret", "Удержание риска организатором", D("-0.1"), D("0.1"), "±10 п.п."),
    ("dmsp", "Потолок: ставка кредита МСП", D("-0.02"), D("0.02"), "±2 п.п.; действует только в режиме «с потолком»"),
    ("kloss", "Множитель реализованных потерь", D("0.5"), D(2), "×0,5 / ×2"),
)
_SENS_BASE = dict(dt=ZERO, kT=ONE, dlgd=ZERO, kpd=ONE, dks=ZERO, dprem=ZERO, dmargin=ZERO,
                  kfix=ONE, dret=ZERO, dmsp=ZERO, kloss=ONE)


def _sens_case(p: FinParams, base: dict, sh: dict, mode: int) -> dict:
    t_c = p.t_days + sh["dt"]
    avg_c = base["avg_bal5"] * (t_c / p.t_days) * sh["kT"]
    T_c = base["T5"] * sh["kT"]
    ks_c = base["ks5"] + sh["dks"]
    prem_c = base["prem_mix5"] + sh["dprem"]
    r_fund_c = ks_c + prem_c
    r_fund_price_c = r_fund_c if p.ks_pass_through == 1 else p.ks_now + prem_c
    lgd_c = min(ONE, p.lgd + sh["dlgd"])
    el_c = pd_port(p) * sh["kpd"] * lgd_c * (ONE - p.cover)
    rel_c = el_c + p.cover * p.ins_rate
    r_cp_c = r_fund_price_c + rel_c + p.r_opex + p.r_margin + sh["dmargin"]
    e_c = p.msp_rate + sh["dmsp"] + p.speed_prem
    cap_c = e_c / (ONE + e_c * t_c / DAYS)
    r_app_c = r_cp_c if mode == 1 else min(r_cp_c, cap_c)
    borne_c = base["w_on5"] + (ONE - base["w_on5"]) * max(ZERO, p.retention + sh["dret"])
    prem_on_c = base["prem_on5"] + sh["dprem"]
    income = avg_c * r_app_c
    fund = avg_c * (r_fund_c - p.eq_switch * p.cap_norm * borne_c * (ks_c + prem_on_c))
    loss = avg_c * el_c * borne_c * p.loss_mult * sh["kloss"]
    ins = avg_c * p.cover * p.ins_rate
    cfa = T_c * base["w_cfa5"] * p.cfa_fee
    var = T_c * p.var_pct
    fix = base["fix5"] * sh["kfix"]
    pbt = income - fund - loss - ins - cfa - var - fix
    return dict(t=t_c, avg=avg_c, turnover=T_c, ks=ks_c, prem=prem_c, r_fund=r_fund_c,
                r_app=r_app_c, borne=borne_c, income=income, fund_net=fund, el_borne=loss,
                ins=ins, cfa_fee=cfa, var_opex=var, fix_opex=fix, pbt=pbt)


def sensitivity(p: FinParams, years: list[dict], scenario: str, mode: int) -> dict:
    r5 = rates(p, scenario, 5)
    base = dict(avg_bal5=years[4]["avg_bal"], T5=years[4]["turnover"], ks5=r5.ks,
                prem_mix5=r5.prem_mix, prem_on5=r5.prem_on, w_on5=r5.w_on, w_cfa5=r5.w_cfa,
                fix5=fixed_opex(p)[4])
    b = _sens_case(p, base, _SENS_BASE, mode)
    rows = []
    for key, name, lo, hi, note in SENS_DRIVERS:
        lo_c = _sens_case(p, base, {**_SENS_BASE, key: _SENS_BASE[key] + lo if key[0] == "d" else lo}, mode)
        hi_c = _sens_case(p, base, {**_SENS_BASE, key: _SENS_BASE[key] + hi if key[0] == "d" else hi}, mode)
        rows.append(dict(key=key, name=name, low=lo, high=hi, note=note,
                         pbt_low=lo_c["pbt"], pbt_high=hi_c["pbt"],
                         delta_low=lo_c["pbt"] - b["pbt"], delta_high=hi_c["pbt"] - b["pbt"],
                         range=abs(hi_c["pbt"] - lo_c["pbt"])))
    return dict(scenario=scenario, mode=mode, base_pbt=b["pbt"], pbt_years=years[4]["pbt"],
                base_inputs=base, rows=rows)


# ---------------------------------------------------------------- стресс

STRESS_SHARES = _vec("0.05", "0.1", "0.15", "0.2", "0.25")
STRESS_LGDS = _vec("0.4", "0.6", "0.8", "1")
STRESS_MONTHS = (12, 24, 36, 48, 60)


def stress(p: FinParams, months: list[dict], years: list[dict], kp: dict, scenario: str) -> dict:
    m = p.stress_month
    if not 1 <= m <= MONTHS:
        raise FinModelError("Месяц события стресса должен быть от 1 до 60")
    y = (m - 1) // 12 + 1
    row = months[m - 1]
    bal = row["bal_end"]
    borne = rates(p, scenario, y).borne
    exposure = bal * p.stress_share
    gross = exposure * p.lgd * (ONE - p.cover)
    loss = gross * borne
    el_year = years[y - 1]["el_borne"]
    capital = row["capital"]
    denom = bal * p.lgd * (ONE - p.cover)
    max_share = capital / (denom * borne) if denom > 0 else ZERO
    grid = [[s * bal * lg * (ONE - p.cover) * borne for lg in STRESS_LGDS] for s in STRESS_SHARES]
    grid_cap = [[(v / capital if capital > 0 else ZERO) for v in r] for r in grid]
    by_month = []
    for mm in STRESS_MONTHS:
        yy = (mm - 1) // 12 + 1
        b = months[mm - 1]["bal_end"]
        c = months[mm - 1]["capital"]
        lo = b * p.stress_share * p.lgd * (ONE - p.cover) * rates(p, scenario, yy).borne
        by_month.append(dict(month=mm, bal=b, capital=c, loss=lo,
                             coverage=(c / lo if lo > 0 else ZERO)))
    return dict(
        month=m, year=y, bal=bal, share=p.stress_share, exposure=exposure, lgd=p.lgd,
        cover=p.cover, gross=gross, borne=borne, loss=loss, el_year=el_year,
        unexpected=max(ZERO, loss - el_year), capital=capital,
        coverage=(capital / loss if loss > 0 else ZERO), np_year=years[y - 1]["np"],
        np_year_with_event=years[y - 1]["np"] - loss, eq_need_peak=kp["eq_need_peak"],
        eq_need_with_event=kp["eq_need_peak"] + loss, max_share=max_share,
        covered=loss <= capital, shares=list(STRESS_SHARES), lgds=list(STRESS_LGDS),
        grid=grid, grid_cap=grid_cap, by_month=by_month,
    )


# ---------------------------------------------------------------- проверки


def checks(p: FinParams, res: dict) -> list[dict]:
    """Контрольные тождества (аналог листа «Проверки», которого нет в книге)."""
    eps = D("1e-9")
    out: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append(dict(name=name, ok=bool(ok), detail=detail))

    months, years = res["months"], res["years"]
    sc, mode = res["scenario"], res["mode"]
    add("Сумма долей рейтингов = 100%", abs(sum(p.rating_shares, ZERO) - 1) < eps)
    for s in SCENARIOS:
        add(f"Веса источников {s} = 100% в каждом году",
            all(abs(weights_sum(p, s, y) - 1) < eps for y in range(1, 6)))
    add("Узлы траектории неотрицательны", min(res["nodes"]) >= 0)
    add("Сумма месяцев = годовой оборот",
        all(abs(years[y]["turnover"] - p.turnover_bn[y] * 1000) < D("1e-6") for y in range(5)))
    add("ПДН года = сумма месяцев", abs(sum((y["pbt"] for y in years), ZERO) - months[-1]["cum_pbt"]) < D("1e-6"))
    add("Налог за 5 лет = ставка × max(0, накопленная ПДН)",
        abs(res["kpis"]["tax_5y"] - p.tax * max(ZERO, months[-1]["cum_pbt"])) < D("1e-6"))
    add("ЧП = ПДН − налог", all(abs(r["np"] - (r["pbt"] - r["tax"])) < eps for r in months))
    add("Накопленная ЧП = сумма ЧП", abs(sum((r["np"] for r in months), ZERO) - months[-1]["cum_np"]) < D("1e-6"))
    add("Остатки неотрицательны", all(r["bal_end"] >= 0 for r in months))
    add("Капитал = норма × доля риска × средний остаток",
        all(abs(r["capital"] - p.cap_norm * r["borne"] * r["avg"]) < eps for r in months))
    ann = next(x for x in res["matrix"] if x["scenario"] == sc and x["mode"] == mode)
    add("Матрица сценариев совпадает с помесячным расчётом",
        all(abs(ann["years"][i]["pbt"] - years[i]["pbt"]) < D("1e-6") for i in range(5)))
    add("Режим 2 не даёт цену выше потолка",
        all(rates(p, s, y).r_cap <= cap_discount(p) + eps for s in SCENARIOS for y in range(1, 6)))
    u = res["unit"]["selected"]
    add("Эффективная ставка = D/(F−D) × 365/t",
        abs(u["eff"] - u["D"] / (u["F"] - u["D"]) * DAYS / u["t"]) < D("1e-12"))
    add("Компоненты счёта в сумме = D",
        abs(u["fund"] + u["el"] + u["opex"] + u["margin"] - u["D"]) < D("1e-9"))
    add("База мини-модели чувствительности ≈ ПДН Г5 (приближение стационарного остатка)",
        abs(res["sensitivity"]["base_pbt"] - years[4]["pbt"]) < D("1e-6"))
    st = res["stress"]
    add("Стресс: потери = ячейка сетки (доля 25%, LGD 60%)",
        p.stress_share not in STRESS_SHARES or p.lgd not in STRESS_LGDS
        or abs(st["grid"][STRESS_SHARES.index(p.stress_share)][STRESS_LGDS.index(p.lgd)] - st["loss"]) < eps)
    return out


# ---------------------------------------------------------------- точка входа


def run(p: FinParams | None = None) -> dict:
    p = p or FinParams()
    if p.scenario not in SCENARIOS:
        raise FinModelError("Сценарий фондирования должен быть A, B, C или M")
    if p.price_mode not in PRICE_MODES:
        raise FinModelError("Режим цены должен быть 1 или 2")
    if p.t_days <= 0:
        raise FinModelError("Срок финансирования должен быть больше нуля")
    if abs(sum(p.rating_shares, ZERO) - 1) > D("1e-9"):
        raise FinModelError("Доли рейтингов якорей должны давать 100%")
    for s in SCENARIOS:
        if abs(sum(p.weights[SCENARIOS.index(s)], ZERO) - 1) > D("1e-9"):
            raise FinModelError(f"Веса источников сценария {s} должны давать 100%")
    sc, mode = p.scenario, p.price_mode
    tr = trajectory(p)
    months = monthly(p, sc, mode)
    years = yearly(p, months, sc, mode)
    kp = kpis(p, months, years)
    res: dict[str, Any] = dict(
        scenario=sc, mode=mode, nodes=tr["nodes"], coefs=balance_coefs(p),
        pd_port=pd_port(p), el_rate=el_rate(p), r_el=r_el(p), cap_credit=cap_credit(p),
        cap_discount=cap_discount(p), msp_discount=cap_discount(p, e=p.msp_rate),
        fund_ceiling=cap_discount(p) - r_el(p) - p.r_opex - p.r_margin,
        fixed_opex=fixed_opex(p), fixed_opex_breakdown=fixed_opex_breakdown(p),
        rates={s: [_rates_dict(rates(p, s, y), p) for y in range(1, 6)] for s in SCENARIOS},
        months=months, years=years, kpis=kp,
        matrix=scenario_matrix(p),
        unit={
            "selected": unit_economics(p, sc, mode),
            "all": [unit_economics(p, s, m) for s in SCENARIOS for m in PRICE_MODES],
        },
        sensitivity=sensitivity(p, years, sc, mode),
    )
    res["stress"] = stress(p, months, years, kp, sc)
    res["warnings"] = warnings(p, res)
    res["checks"] = checks(p, res)
    return res


def _rates_dict(r: Rates, p: FinParams) -> dict:
    return dict(year=r.year, ramp=r.ramp, w=r.w, w_on=r.w_on, prem_mix=r.prem_mix,
                prem_on=r.prem_on, ks=r.ks, r_fund=r.r_fund, borne=r.borne,
                r_fund_price=r.r_fund_price, r_cp=r.r_cp, r_cap=r.r_cap,
                eff_cp=eff_rate(r.r_cp, p.t_days), eff_cap=eff_rate(r.r_cap, p.t_days),
                margin_cp=r.margin(1, p), margin_cap=r.margin(2, p))


def warnings(p: FinParams, res: dict) -> list[dict]:
    """Плашки-предупреждения экрана «Портфельная модель» (раздел 2.4, п. 5)."""
    out = []
    y5 = res["years"][4]
    if y5["eff"] > cap_credit(p) + D("1e-12"):
        out.append(dict(code="price_above_cap", level="warning",
                        text="Цена выше потолка рынка",
                        detail="Эффективная ставка поставщика в Г5 выше потолка "
                               "(кредит МСП + премия за скорость)."))
    if res["kpis"]["cum_np_5y"] < 0:
        out.append(dict(code="cum_np_negative", level="warning",
                        text="Накопленная прибыль за 5 лет отрицательна",
                        detail="Модель не окупается в горизонте 60 месяцев."))
    if not res["stress"]["covered"]:
        out.append(dict(code="capital_not_covering", level="danger",
                        text="Капитал под риск не покрывает дефолт якоря",
                        detail="Нужен меньший лимит на якорь, страхование или больше капитала."))
    if any(y["margin"] < 0 for y in res["years"]):
        out.append(dict(code="negative_margin", level="danger",
                        text="Маржа платформы отрицательна",
                        detail="Цена с потолком рынка не покрывает фондирование, потери и издержки."))
    return out


def to_jsonable(x: Any) -> Any:
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {k: to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    return x


DEFAULTS = FinParams()

