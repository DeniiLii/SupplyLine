from decimal import Decimal as D

from engine.funding import allocate, off_balance_share, scenario_rate
from engine.portfolio import Exposure, check_limits, first_failed, supplier_limit


def book():
    return [Exposure(1, 10, "nonfood", D(200e6)), Exposure(2, 11, "diy", D(150e6)),
            Exposure(3, 12, "food", D(100e6))]


def test_concentration_blocks_with_rule():
    checks = check_limits(new=Exposure(1, 10, "nonfood", D(60e6)), book=book(), anchor_limit=D(500e6),
                          supplier_limit_value=D(500e6), program_size=D(1e9))
    bad = first_failed(checks)
    assert bad is not None and "25%" in bad.rule
    assert bad.used == D(260e6) and bad.limit == D(250e6)


def test_supplier_limit_blocks_first():
    checks = check_limits(new=Exposure(2, 11, "diy", D(10e6)), book=book(), anchor_limit=D(500e6),
                          supplier_limit_value=D(155e6), program_size=D(1e9))
    assert first_failed(checks).rule == "Лимит поставщика"


def test_ok():
    checks = check_limits(new=Exposure(3, 12, "food", D(5e6)), book=book(), anchor_limit=D(500e6),
                          supplier_limit_value=D(500e6), program_size=D(1e9))
    assert first_failed(checks) is None


def test_supplier_limit_formula():
    assert supplier_limit(D("0.7"), D(100e6), D(50e6)) == D(50e6)
    assert supplier_limit(D("0.7"), D(50e6), D(50e6)) == D(35e6)


def test_funding_scenarios():
    assert scenario_rate("A") == D("0.15")
    assert scenario_rate("C") == D("0.185")
    assert abs(scenario_rate("M") - D("0.15975")) < D("1e-12")
    assert off_balance_share("M") == D("0.40")
    seq = [allocate("M", i) for i in range(200)]
    assert seq.count("bank") == 120 and seq.count("cfa") == 50
