from decimal import Decimal as D

import pytest

from engine import lifecycle
from engine.pricing import PriceInput, max_premium_for_msp_parity, price, stationary_scale


def ref(**kw) -> PriceInput:
    base = dict(face=D(10_000_000), t_days=45, r_fund=D("0.16"), pd=D("0.01"), lgd=D("0.6"), cover=D(0),
                r_opex=D("0.012"), r_margin=D("0.024"))
    base.update(kw)
    return PriceInput(**base)


def test_reference_invoice():
    p = price(ref())
    assert p.r_total == D("0.202")
    assert p.discount == D("249041.10")
    assert p.payout == D("9750958.90")
    assert p.comp_funding == D("197260.27")
    assert p.comp_loss == D("7397.26")
    assert p.comp_opex == D("14794.52")
    assert p.comp_margin == D("29589.05")
    assert p.comp_funding + p.comp_loss + p.comp_opex + p.comp_margin == p.discount
    assert p.spread == D("51780.82")
    assert abs(p.spread_pct_cycle - D("0.005178")) < D("0.000001")
    assert abs(p.eff_rate - D("0.2072")) <= D("0.0002")


def test_key_rate_14_is_above_msp():
    p = price(ref(r_fund=D("0.15")))
    assert p.r_total == D("0.192")
    assert abs(p.eff_rate - D("0.197")) < D("0.001")
    assert p.eff_rate > D("0.18")
    assert not p.cheaper_than_msp


def test_cap_mode_never_above_cap_and_margin_residual():
    p = price(ref(r_fund=D("0.185"), mode=2))
    assert p.capped
    assert p.r_total <= p.r_cap
    assert abs(p.eff_rate - D("0.19")) < D("0.0001")
    assert p.r_margin_effective < 0  # ЦФА с потолком: остаточная маржа отрицательна


def test_scale_stationary():
    s = stationary_scale(D(150_000_000_000), 45, D("0.6"), D("0.1"), D("0.64"), D("0.20175"), D("0.15975"))
    assert abs(s["avg_balance"] / D(1e9) - D("18.49")) < D("0.01")
    assert abs(s["on_balance"] / D(1e9) - D("11.10")) < D("0.01")
    assert abs(s["capital"] / D(1e9) - D("1.18")) < D("0.01")
    assert abs(s["spread"] / D(1e9) - D("0.78")) < D("0.01")


@pytest.mark.parametrize("field,lo,hi", [
    ("t_days", 30, 60), ("r_fund", D("0.14"), D("0.18")), ("pd", D("0.005"), D("0.04")),
    ("lgd", D("0.4"), D("0.9")),
])
def test_monotone_up(field, lo, hi):
    assert price(ref(**{field: lo})).discount < price(ref(**{field: hi})).discount


def test_monotone_cover_and_full_cover():
    assert price(ref(cover=D("0.5"))).discount < price(ref(cover=D(0))).discount
    p = price(ref(cover=D(1)))
    assert p.comp_loss == 0


def test_parity_premium():
    prem = max_premium_for_msp_parity(D("0.14"), D("0.01"), D("0.6"), D(0), D("0.012"), D("0.024"), 45)
    p = price(ref(r_fund=D("0.14") + prem))
    assert abs(p.eff_rate - D("0.18")) < D("0.0001")
    assert prem < D("0.01")  # даже банк-партнёр (KС + 1 п.п.) не укладывается в паритет


@pytest.mark.parametrize("bad", [dict(face=D(0)), dict(t_days=0), dict(pd=D("-0.1")), dict(lgd=D("1.5"))])
def test_validation(bad):
    with pytest.raises(ValueError):
        price(ref(**bad))


def test_state_machine():
    S = lifecycle.Status
    path = [S.DRAFT, S.UPD_VERIFIED, S.ACCEPTED, S.OFFERED, S.SOLD, S.FUNDED, S.REPAID]
    for a, b in zip(path, path[1:]):
        assert lifecycle.transition(a, b) == b
    for a, b in [(S.DRAFT, S.FUNDED), (S.REPAID, S.OVERDUE), (S.OFFERED, S.REPAID), (S.REJECTED, S.SOLD)]:
        with pytest.raises(lifecycle.TransitionError):
            lifecycle.transition(a, b)
    assert lifecycle.transition(S.OVERDUE, S.REGRESS) == S.REGRESS
    assert lifecycle.transition(S.REGRESS, S.WRITTEN_OFF) == S.WRITTEN_OFF
