"""Эталон финансовой модели: таблицы раздела 2.4 промпта (базовый вариант M, цена по формуле)."""

from decimal import Decimal

import pytest

from engine import finmodel as fm
from engine.finmodel import FinModelError, FinParams, run

MONEY = 0.05  # ₽ млн
RATE = 1e-6


@pytest.fixture(scope="module")
def base():
    return run()


def approx(x, ref, tol=MONEY):
    assert x is not None
    assert abs(float(x) - ref) <= tol, f"{float(x)} != {ref}"


YEARS_REF = {
    "turnover": [8000, 22000, 50000, 90000, 150000],
    "avg_bal": [863.3, 2599.1, 5826.1, 10760.0, 17844.7],
    "bal_end": [1771.7, 3422.2, 8312.6, 13205.1, 22598.8],
    "income": [165.8, 519.3, 1175.4, 2170.8, 3600.2],
    "fund_net": [116.5, 382.4, 874.8, 1615.6, 2679.4],
    "el_borne": [5.2, 11.1, 22.4, 41.3, 68.5],
    "cfa_fee": [0.0, 2.2, 6.3, 11.2, 18.8],
    "var_opex": [2.4, 6.6, 15.0, 27.0, 45.0],
    "fix_opex": [253.0, 360.4, 478.3, 567.3, 658.1],
    "pbt": [-211.4, -243.3, -221.2, -91.7, 130.4],
    "np": [-211.4, -243.3, -221.2, -91.7, 130.4],
    "cum_np": [-211.4, -454.7, -676.0, -767.7, -637.2],
    "capital_avg": [86.3, 185.1, 372.9, 688.6, 1142.1],
}


@pytest.mark.parametrize("key", list(YEARS_REF))
def test_years(base, key):
    for y, ref in zip(base["years"], YEARS_REF[key]):
        # Эталон дан с одним знаком: допуск — половина последнего разряда плюс 0,05.
        approx(y[key], ref, 0.1)


def test_year_rates(base):
    r = [0.1920, 0.1998, 0.2018, 0.2018, 0.2018]
    e = [0.1967, 0.2048, 0.2069, 0.2069, 0.2069]
    won = [1.0, 0.68, 0.60, 0.60, 0.60]
    borne = [1.0, 0.712, 0.64, 0.64, 0.64]
    be = [42253, 64719, 87541, 103847, 120453]
    for i, y in enumerate(base["years"]):
        approx(y["r_app"], r[i], 0.0001)
        approx(y["eff"], e[i], 0.0001)
        approx(y["w_on"], won[i], RATE)
        approx(y["borne"], borne[i], RATE)
        approx(y["breakeven_turnover"], be[i], 1)


def test_kpis(base):
    k = base["kpis"]
    approx(k["eq_need_peak"], 2058.1)
    assert k["eq_need_peak_month"] == 60
    assert k["first_positive_np_month"] == 48
    assert k["sustained_positive_month"] == 51
    assert k["payback_month"] is None
    approx(k["cum_np_bottom"], -775.0)
    assert k["cum_np_bottom_month"] == 50
    approx(k["cum_np_5y"], -637.2)
    approx(k["breakeven_turnover_y5"], 120453, 1)
    approx(k["breakeven_share_y5"], 0.80, 0.005)
    assert k["tax_5y"] == 0
    neg = [m["np"] for m in base["months"] if m["month"] in (49, 50)]
    assert all(x < 0 for x in neg)


def test_service_values(base):
    nodes = [0.0, 1230.8, 2343.2, 5709.6, 9015.0, 15448.9]
    for v, ref in zip(base["nodes"], nodes):
        approx(v, ref)
    c0, c1, c2 = base["coefs"]
    approx(c0, 1.0, 1e-4)
    approx(c1, 0.4795, 1e-4)
    approx(c2, 0.0, 1e-4)
    approx(base["r_el"], 0.006, RATE)
    approx(base["pd_port"], 0.01, RATE)
    approx(base["cap_discount"], 0.18565, 1e-5)


MONTHS_REF = {
    1: (102.564, 102.564, 51.282, -20.896, -20.896, -20.896, 26.024),
    2: (205.128, 254.303, 178.433, -20.387, -20.387, -41.283, 59.126),
    12: (1230.769, 1771.689, 1695.820, -14.245, -14.245, -211.371, 380.953),
    13: (1323.471, 1913.566, 1842.628, -23.126, -23.126, -234.498, 365.693),
    24: (2343.195, 3422.199, 3353.625, -17.439, -17.439, -454.714, 693.492),
    36: (5709.604, 8312.583, 8105.064, -10.023, -10.023, -675.962, 1194.686),
    48: (9014.950, 13205.124, 13001.370, 0.636, 0.636, -767.653, 1599.741),
    60: (15448.888, 22598.825, 22202.213, 26.960, 26.960, -637.204, 2058.146),
}


@pytest.mark.parametrize("m", list(MONTHS_REF))
def test_control_months(base, m):
    row = base["months"][m - 1]
    keys = ("turnover", "bal_end", "avg", "pbt", "np", "cum_np", "eq_need")
    for k, ref in zip(keys, MONTHS_REF[m]):
        approx(row[k], ref, 0.001)


MATRIX_REF = {
    ("A", 1): ([-211.4, -234.4, -196.1, -45.6, 207.0], -480.5, 0.1967, 0.0240, 109903, 2701),
    ("A", 2): ([-216.9, -250.9, -233.1, -113.9, 93.7], -721.0, 0.1900, 0.0177, 126430, 2941),
    ("B", 1): ([-210.1, -230.5, -187.4, -29.4, 233.8], -423.6, 0.2124, 0.0240, 106610, 2644),
    ("B", 2): ([-228.5, -286.0, -311.8, -259.2, -147.2], -1232.6, 0.1900, 0.0027, 185864, 3453),
    ("C", 1): ([-222.4, -266.5, -268.3, -177.7, -12.5], -947.4, 0.2335, 0.0240, 146593, 1169),
    ("C", 2): ([-258.1, -373.9, -509.2, -622.6, -750.4], -2514.2, 0.1900, -0.0173, None, 2736),
    ("M", 1): ([-211.4, -243.3, -221.2, -91.7, 130.4], -637.2, 0.2069, 0.0240, 120453, 2058),
    ("M", 2): ([-216.9, -280.1, -315.0, -264.9, -156.8], -1233.8, 0.1900, 0.0079, 189184, 2655),
}


@pytest.mark.parametrize("key", list(MATRIX_REF))
def test_matrix(base, key):
    x = next(r for r in base["matrix"] if (r["scenario"], r["mode"]) == key)
    pbt, cum, eff, margin, be, cap = MATRIX_REF[key]
    for v, ref in zip(x["pbt"], pbt):
        approx(v, ref, 0.1)
    approx(x["np5"], pbt[-1], 0.1)
    approx(x["cum_np5"], cum, 0.1)
    approx(x["eff5"], eff, 0.0001)
    approx(x["margin5"], margin, 0.0001)
    if be is None:
        assert x["breakeven5"] is None
    else:
        approx(x["breakeven5"], be, 1)
    approx(x["eq_need"], cap, 1)


UNIT_REF = {
    ("A", 1): (0.1920, 0.1967, 118.36, 4881.64, 92.47, 3.70, 7.40, 14.79, 2.96, 10.02),
    ("A", 2): (0.1857, 0.1900, 114.44, 4885.56, 92.47, 3.70, 7.40, 10.88, 2.18, 6.02),
    ("B", 1): (0.2070, 0.2124, 127.60, 4872.40, 101.71, 3.70, 7.40, 14.79, 2.96, 19.48),
    ("B", 2): (0.1857, 0.1900, 114.44, 4885.56, 101.71, 3.70, 7.40, 1.63, 0.33, 6.02),
    ("C", 1): (0.2270, 0.2335, 139.93, 4860.07, 114.04, 3.70, 7.40, 14.79, 2.96, 32.08),
    ("C", 2): (0.1857, 0.1900, 114.44, 4885.56, 114.04, 3.70, 7.40, -10.69, -2.14, 6.02),
    ("M", 1): (0.2018, 0.2069, 124.37, 4875.63, 98.48, 3.70, 7.40, 14.79, 2.96, 16.17),
    ("M", 2): (0.1857, 0.1900, 114.44, 4885.56, 98.48, 3.70, 7.40, 4.87, 0.97, 6.02),
}


@pytest.mark.parametrize("key", list(UNIT_REF))
def test_unit(base, key):
    u = next(r for r in base["unit"]["all"] if (r["scenario"], r["mode"]) == key)
    ref = UNIT_REF[key]
    approx(u["r"], ref[0], 0.0001)
    approx(u["eff"], ref[1], 0.0001)
    keys = ("D", "recv", "fund", "el", "opex", "margin", "margin_per_1000", "overpay")
    for k, r in zip(keys, ref[2:]):
        approx(u[k], r, 0.006)


SENS_REF = [
    (-284.1, 284.1), (-236.6, 236.6), (-12.8, 12.8), (-19.3, 38.5), (-34.3, 34.3), (-11.4, 11.4),
    (-178.4, 178.4), (131.6, -131.6), (-6.4, 6.4), (0.0, 0.0), (34.3, -68.5),
]


def test_sensitivity(base):
    s = base["sensitivity"]
    approx(s["base_pbt"], 130.4, 0.05)
    assert len(s["rows"]) == 11
    for row, (lo, hi) in zip(s["rows"], SENS_REF):
        approx(row["delta_low"], lo, 0.05)
        approx(row["delta_high"], hi, 0.05)


def test_sensitivity_cap_mode():
    s = run(FinParams(price_mode=2))["sensitivity"]
    approx(s["base_pbt"], -156.8, 0.05)
    msp = next(r for r in s["rows"] if r["key"] == "dmsp")
    approx(msp["delta_low"], -341.6, 0.05)
    approx(msp["delta_high"], 287.3, 0.05)


def test_stress(base):
    st = base["stress"]
    approx(st["bal"], 10760.1, 0.05)
    approx(st["exposure"], 2690.0, 0.05)
    approx(st["gross"], 1614.0, 0.05)
    approx(st["loss"], 1033.0, 0.05)
    approx(st["capital"], 675.6, 0.05)
    approx(st["coverage"], 0.654, 0.001)
    approx(st["el_year"], 41.3, 0.05)
    approx(st["max_share"], 0.164, 0.001)
    approx(st["eq_need_with_event"], 3091.1, 0.05)
    assert not st["covered"]


def test_warnings(base):
    codes = {w["code"] for w in base["warnings"]}
    assert {"price_above_cap", "cum_np_negative", "capital_not_covering"} <= codes
    c2 = run(FinParams(scenario="C", price_mode=2))
    assert "negative_margin" in {w["code"] for w in c2["warnings"]}


# ---------------------------------------------------------------- свойства (раздел 8, п. 10)


def test_checks_all_green(base):
    bad = [c for c in base["checks"] if not c["ok"]]
    assert not bad, bad
    assert len(base["checks"]) >= 18


@pytest.mark.parametrize("sc", fm.SCENARIOS)
@pytest.mark.parametrize("mode", fm.PRICE_MODES)
def test_properties_all_variants(sc, mode):
    res = run(FinParams(scenario=sc, price_mode=mode))
    assert all(c["ok"] for c in res["checks"]), [c for c in res["checks"] if not c["ok"]]
    for y in res["years"]:
        approx(y["turnover"], float(FinParams().turnover_bn[y["year"] - 1]) * 1000, 1e-6)
    p = FinParams()
    if mode == 2:
        for y in range(1, 6):
            assert fm.rates(p, sc, y).r_cap <= fm.cap_discount(p)


def test_negative_nodes_rejected():
    with pytest.raises(FinModelError):
        run(FinParams().with_overrides(turnover_bn=[8, 22, 50, 90, 10]))


def test_breakeven_na_for_c_cap():
    x = next(r for r in run()["matrix"] if (r["scenario"], r["mode"]) == ("C", 2))
    assert x["breakeven5"] is None
    assert x["years"][-1]["cm"] <= 0


def test_tax_identity_when_profitable():
    p = FinParams(scenario="B", turnover_bn=tuple(Decimal(x) for x in (40, 80, 120, 160, 200)))
    res = run(p)
    cum = res["months"][-1]["cum_pbt"]
    assert cum > 0
    assert abs(res["kpis"]["tax_5y"] - p.tax * cum) < Decimal("1e-9")


def test_variants_run():
    for ks in (1, 2, 3):
        for pt in (1, 2):
            for t in (30, 45, 60):
                res = run(FinParams(ks_scenario=ks, ks_pass_through=pt, t_days=Decimal(t)))
                assert all(c["ok"] for c in res["checks"])


# ---------------------------------------------------------------- граница позиции цены (WP1)


def test_position_at_cap_is_within_premium():
    p = FinParams()
    cap = fm.cap_credit(p)
    assert fm.price_position(p, cap) == "дороже кредита, в пределах премии"
    assert fm.price_position(p, cap + Decimal("1e-34")) == "дороже кредита, в пределах премии"
    assert fm.price_position(p, cap + Decimal("1e-6")) == "выше потолка рынка"


def test_position_at_msp_is_cheaper():
    p = FinParams()
    assert fm.price_position(p, p.msp_rate) == "дешевле кредита МСП"
    assert fm.price_position(p, p.msp_rate + Decimal("1e-34")) == "дешевле кредита МСП"
    assert fm.price_position(p, p.msp_rate + Decimal("1e-6")) == "дороже кредита, в пределах премии"


@pytest.mark.parametrize("t", [30, 45, 60])
def test_capped_mode_stays_within_premium(t):
    # Режим 2 ставит eff ровно на потолок; при сроке 30 Decimal раньше давал +1e-34 и «выше потолка»
    p = FinParams(t_days=Decimal(t))
    for sc in "ABCM":
        assert fm.unit_economics(p, sc, 2)["position"] == "дороже кредита, в пределах премии"
