import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        yield c


def test_health_and_meta(client):
    assert client.get("/api/health").json() == {"ok": True}
    m = client.get("/api/meta").json()
    assert "Демо-прототип" in m["disclaimer"]
    assert len(m["facts"]) >= 12 and len(m["layers"]) == 7 and len(m["roadmap"]) == 4


def test_quote_contract(client):
    r = client.post("/api/pricing/quote", json={"face": 10000000, "t_days": 45, "key_rate": 0.14,
                                                "source": "bank", "rating": "B"})
    assert r.status_code == 200
    j = r.json()
    assert abs(j["price"]["r_total"] - 0.192) < 1e-9
    assert j["price"]["eff_rate"] > 0.18
    assert j["verdict"]["kind"] == "more_expensive"
    assert sum(w["amount"] for w in j["waterfall"]) == pytest.approx(j["price"]["discount"], abs=0.001)
    assert len(j["premium_curve"]) > 10


@pytest.mark.parametrize("body", [
    {"face": -1}, {"t_days": 0}, {"lgd": 1.5}, {"cover": 0.95}, {"rating": "Z"},
    {"source": "mix", "weights": {"bank": 0.5, "cfa": 0.2}}, {"unknown": 1},
])
def test_quote_validation(client, body):
    r = client.post("/api/pricing/quote", json=body)
    assert r.status_code == 422
    assert r.json()["code"] == "validation"


def test_finmodel_defaults_and_run(client):
    d = client.get("/api/finmodel/defaults").json()
    assert any(p["key"] == "ks_now" and p["badge"] == "Факт" for p in d["params"])
    r = client.post("/api/finmodel/run", json={}).json()
    y5 = r["years"][4]
    assert round(y5["pbt"], 1) == 130.4
    assert round(r["kpis"]["cum_np_5y"], 1) == -637.2
    assert round(r["kpis"]["eq_need_peak"]) == 2058
    assert round(r["kpis"]["breakeven_turnover_y5"]) == 120453
    assert {w["code"] for w in r["warnings"]} >= {"price_above_cap", "cum_np_negative", "capital_not_covering"}
    assert len(r["months"]) == 60 and len(r["matrix"]) == 8
    c2 = client.post("/api/finmodel/run", json={"scenario": "C", "price_mode": 2, "months": False}).json()
    assert "negative_margin" in {w["code"] for w in c2["warnings"]}
    assert "months" not in c2


@pytest.mark.parametrize("body", [
    {"t_days": 0}, {"t_days": 120}, {"scenario": "X"}, {"weights_m": [0.5, 0, 0.2, 0.1, 0.1]},
    {"turnover_bn": [8, 22, 50, 90, -1]}, {"lgd": -0.1},
])
def test_finmodel_validation(client, body):
    assert client.post("/api/finmodel/run", json=body).status_code == 422


def test_finmodel_negative_nodes(client):
    r = client.post("/api/finmodel/run", json={"turnover_bn": [8, 22, 50, 90, 10]})
    assert r.status_code == 422 and "минус" in r.json()["detail"]


def test_excel_download(client):
    r = client.get("/api/finmodel/excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r2 = client.post("/api/finmodel/excel", json={"scenario": "A", "t_days": 60})
    assert r2.status_code == 200 and r2.content[:2] == b"PK"


def test_invoices_and_demo_script(client):
    lst = client.get("/api/invoices", params={"limit": 500}).json()
    assert lst["total"] > 500
    big = next(i for i in lst["items"] if i["story"] == "concentration")
    # Крупный счёт упирается в потолок концентрации
    r = client.post(f"/api/invoices/{big['id']}/sell")
    assert r.status_code == 422 and r.json()["rule"] == "Концентрация на одного якоря: не больше 15%"
    # Обычное предложение продаётся
    offer = next(i for i in lst["items"] if i["status"] == "OFFERED" and i["story"] is None
                 and not i["review_flag"] and not i["status_reason"])
    r = client.post(f"/api/invoices/{offer['id']}/sell")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SOLD"
    # Повторная продажа того же требования блокируется реестром
    r = client.post(f"/api/invoices/{offer['id']}/resell")
    assert r.status_code == 409 and r.json()["claim_key"]
    # Повторная продажа через «Продать» тоже невозможна
    assert client.post(f"/api/invoices/{offer['id']}/sell").status_code == 409
    # +1 день: деньги пришли
    client.post("/api/clock/advance", json={"days": 1})
    assert client.get(f"/api/invoices/{offer['id']}").json()["status"] == "FUNDED"
    # Просрочка якоря и регресс через 30 дней
    r = client.post(f"/api/invoices/{offer['id']}/overdue")
    assert r.json()["status"] == "OVERDUE"
    client.post("/api/clock/advance", json={"days": 30})
    assert client.get(f"/api/invoices/{offer['id']}").json()["status"] == "REGRESS"
    ov = client.get("/api/overview").json()
    assert ov["kpi"]["overdue30_amount"] > 0
    assert {g["key"] for g in ov["gates"]} >= {"approval", "overdue30", "fraud", "time_to_money", "external"}


def test_invalid_transition_and_404(client):
    lst = client.get("/api/invoices", params={"status": "REPAID", "limit": 1}).json()
    rid = lst["items"][0]["id"]
    assert client.post(f"/api/invoices/{rid}/sell").status_code == 409
    assert client.post(f"/api/invoices/{rid}/overdue").status_code == 409
    assert client.get("/api/invoices/999999").status_code == 404


def test_mock_failure_payment(client):
    lst = client.get("/api/invoices", params={"status": "OFFERED", "limit": 50}).json()
    offer = next(i for i in lst["items"] if i["story"] is None and not i["review_flag"] and not i["status_reason"])
    client.put("/api/settings", json={"payment_fails": True})
    r = client.post(f"/api/invoices/{offer['id']}/sell")
    assert r.status_code == 503
    client.put("/api/settings", json={"payment_fails": False})
    assert client.get(f"/api/invoices/{offer['id']}").json()["status"] == "OFFERED"


def test_roles(client):
    assert client.get("/api/suppliers/1").status_code == 200
    a = client.get("/api/anchors/1").json()
    assert a["anchor"]["rating"] in "ABCD" and a["scoring"]["rules"]
    inv = client.get("/api/investor", params={"cover": 0.5}).json()
    assert "эмитент" in inv["legal_note"]
    assert inv["expected_loss"] <= inv["expected_loss_no_cover"]


def test_settings_validation(client):
    assert client.put("/api/settings", json={"scenario": "Q"}).status_code == 422
    assert client.post("/api/clock/advance", json={"days": -1}).status_code == 422


def test_anchor_cap_setting(client):
    from sqlalchemy import select

    from api import services as sv
    from db.models import Invoice, SessionLocal

    client.post("/api/demo/reset")
    assert client.get("/api/state").json()["anchor_cap"] == 0.15
    assert client.get("/api/overview").json()["anchor_cap"] == 0.15
    assert client.put("/api/settings", json={"anchor_cap": 0.3}).status_code == 422
    assert client.put("/api/settings", json={"anchor_cap": 0.01}).status_code == 422
    # Прежнее поведение: при 25% крупный счёт упирается в потолок 25%
    assert client.put("/api/settings", json={"anchor_cap": 0.25}).json()["anchor_cap"] == 0.25
    with SessionLocal() as s:
        big = s.scalar(select(Invoice).where(Invoice.story == "concentration"))
        bad = [c for c in sv.limit_checks(s, big) if not c.ok]
    assert [c.rule for c in bad] == ["Концентрация на одного якоря: не больше 25%"]
    client.post("/api/demo/reset")


def test_concentration_story_tuning(client):
    """Перебор суммы сюжетного счёта: он упирается в потолок 15%, открытые предложения того же якоря — нет."""
    from sqlalchemy import select

    from api import services as sv
    from db.models import Invoice, SessionLocal

    client.post("/api/demo/reset")
    with SessionLocal() as s:
        big = s.scalar(select(Invoice).where(Invoice.story == "concentration"))
        others = s.scalars(select(Invoice).where(Invoice.status == "OFFERED", Invoice.story.is_(None),
                                                 Invoice.anchor_id == big.anchor_id)).all()
        assert others
        top = max(i.amount_kop for i in others) / 100 / 1e6
        for amount_mln in (top + 3, 25, 30, 39.5):
            if amount_mln <= top + 2:
                continue
            big.amount_kop = int(amount_mln * 1e6 * 100)
            sv.tune_concentration_story(s)
            assert [c.rule for c in sv.limit_checks(s, big) if not c.ok] ==                 ["Концентрация на одного якоря: не больше 15%"], amount_mln
            for inv in others:
                assert all(c.ok for c in sv.limit_checks(s, inv) if c.rule.startswith("Концентрация")),                     (amount_mln, inv.number)
        s.rollback()


LEVER_SNAPSHOT = {
    # key: (месяц окупаемости, накопленная ЧП 5 лет, пик капитала, ЧП Г5, эфф. ставка Г5, стресс покрыт)
    "base": (None, -637.2041076688105, 2058.145733026977, 130.44936439198082, 0.20689618841246485, False),
    "bank": (None, -480.4615187540041, 2700.682808376139, 207.01613647158754, 0.1966550679088562, False),
    "t60": (58, 106.66238702136056, 2835.760616869264, 465.8915428802998, 0.1982573271472219, False),
    "m35": (50, 520.0085086921442, 2422.4144951984804, 587.9054220696783, 0.2100079360580466, False),
    "cap15": (None, -637.2041076688105, 2058.145733026977, 130.44936439198082, 0.20689618841246485, True),
}


def test_levers_presets(client):
    import time

    t = time.time()
    r = client.get("/api/finmodel/levers")
    assert r.status_code == 200 and time.time() - t < 1
    j = r.json()
    assert "Гипотеза" in j["label"]
    got = {p["key"]: p for p in j["presets"]}
    assert list(got) == list(LEVER_SNAPSHOT)
    for key, (pay, cum, eq, np5, eff, cov) in LEVER_SNAPSHOT.items():
        p = got[key]
        assert p["payback_month"] == pay
        for name, ref in (("cum_np_5y", cum), ("eq_need_peak", eq), ("np5", np5), ("eff5", eff)):
            assert abs(p[name] - ref) <= 1e-6 * max(1, abs(ref)), (key, name)
        assert p["stress_covered"] is cov
        assert len(p["cum_np"]) == 60
        assert p["above_cap"] == (p["eff5"] > p["cap_rate"])
        assert p["position"] in ("дешевле кредита МСП", "дороже кредита, в пределах премии", "выше потолка рынка")
