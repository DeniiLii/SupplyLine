"""Песочница на посетителя (WP5): изоляция состояния, сброс только своей сессии, конфиги имитаций."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from adapters import mocks
from api import sandbox
from api.main import app
from db.models import engine
from db.seed import seed


@pytest.fixture(scope="module")
def template():
    seed()
    with engine.connect() as c:
        c.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))


@pytest.fixture()
def sb(template, monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox, "ENABLED", True)
    monkeypatch.setattr(sandbox, "SESSIONS_DIR", tmp_path)
    monkeypatch.setattr(sandbox, "limiter", sandbox.RateLimiter(10_000))
    monkeypatch.setattr(sandbox, "ip_limiter", sandbox.RateLimiter(10_000))
    sandbox.mark_ready()
    yield tmp_path
    for sid in list(sandbox._engines):
        sandbox._drop_engine(sid)


def _now(c):
    return c.get("/api/state").json()["now"]


def test_cookie_issued_and_reused(sb):
    c = TestClient(app)
    r = c.get("/api/state")
    sid = r.cookies.get("sl_sid")
    assert sandbox.valid_sid(sid)
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    r2 = c.get("/api/state")
    assert "set-cookie" not in r2.headers
    assert (sb / f"{sid}.sqlite3").exists()


def test_clock_isolated(sb):
    a, b = TestClient(app), TestClient(app)
    t0 = _now(a)
    assert _now(b) == t0
    a.post("/api/clock/advance", json={"days": 30})
    assert _now(a) != t0
    assert _now(b) == t0


def test_reset_only_own_session(sb):
    a, b = TestClient(app), TestClient(app)
    t0 = _now(a)
    a.post("/api/clock/advance", json={"days": 7})
    b.post("/api/clock/advance", json={"days": 30})
    tb = _now(b)
    assert a.post("/api/demo/reset").json() == {"reset": "session"}
    assert _now(a) == t0
    assert _now(b) == tb


def test_mock_settings_isolated(sb):
    a, b = TestClient(app), TestClient(app)
    a.put("/api/settings", json={"payment_fails": True})
    assert a.get("/api/state").json()["mocks"]["payment_fails"] is True
    assert b.get("/api/state").json()["mocks"]["payment_fails"] is False
    offer = next(i for i in b.get("/api/invoices", params={"status": "OFFERED", "limit": 50}).json()["items"]
                 if i["story"] != "concentration" and not i["review_flag"])
    r = b.post(f"/api/invoices/{offer['id']}/sell")
    assert r.status_code == 200, r.json()


def test_mock_config_is_request_scoped():
    import contextvars

    def other():
        mocks.set_config(mocks.MockConfig(payment_fails=True))
        return mocks.current_config().payment_fails

    assert contextvars.copy_context().run(other) is True
    assert mocks.current_config().payment_fails is False


def test_rate_limit_and_body(sb, monkeypatch):
    monkeypatch.setattr(sandbox, "limiter", sandbox.RateLimiter(3))
    c = TestClient(app)
    codes = [c.get("/api/state").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    r = TestClient(app).post("/api/pricing/quote", content=b"{" + b" " * 70_000 + b"}",
                             headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_security_headers_and_health(sb):
    r = TestClient(app).get("/api/health")
    assert r.json() == {"ok": True} and "set-cookie" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_cleanup_removes_old(sb):
    c = TestClient(app)
    c.get("/api/state")
    assert sandbox.cleanup(now=time.time() + sandbox.TTL_SECONDS + 1) == 1
    assert not list(sb.glob("*.sqlite3"))


def test_warming_up(sb, monkeypatch):
    monkeypatch.setattr(sandbox, "_ready", sandbox.threading.Event())
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    r = c.get("/api/state")
    assert r.status_code == 503 and r.json()["code"] == "warming_up"
    assert "Готовим демо" in c.get("/").text
