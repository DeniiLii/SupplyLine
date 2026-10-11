from decimal import Decimal as D

from engine.scoring import AnchorMetrics, SupplierMetrics, score_anchor, supplier_limit_share


def test_strong_anchor_is_a():
    r = score_anchor(AnchorMetrics(D("1.2"), 2, D("0.01"), 15))
    assert r.rating == "A" and r.pd == D("0.005") and r.points == 100
    assert all(x["points"] > 0 for x in r.rules)


def test_weak_anchor_c_and_rules_explain():
    r = score_anchor(AnchorMetrics(D("2.8"), 14, D("0.04"), 8))
    assert r.rating == "C" and r.pd == D("0.02")
    texts = [x["rule"] for x in r.rules]
    assert any("просрочка" in t.lower() for t in texts)


def test_rating_d():
    assert score_anchor(AnchorMetrics(D("5"), 30, D("0.2"), 2)).rating == "D"


def test_supplier_scoring_affects_limit_only():
    long = supplier_limit_share(SupplierMetrics(D(1000), D(1e8), 30, D("0.01")))[0]
    new = supplier_limit_share(SupplierMetrics(D(1000), D(1e8), 3, D("0.08")))[0]
    assert long > new
