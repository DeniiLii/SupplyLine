"""Смоук-тест развёрнутого демо: python scripts/smoke.py <base_url> [--wait 60]

Проверяет здоровье, дату фактов, расчёт цены, загрузку интерфейса и изоляцию двух посетителей
(разные cookie: «+30 дней» и сброс у первого не меняют состояние второго). Код выхода 1 при любой ошибке.
Только стандартная библиотека: запускается где угодно.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXPECTED_EFF = 0.1967


class Visitor:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def raw(self, path: str, data: dict | None = None, method: str | None = None) -> tuple[int, bytes, dict]:
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=body, method=method or ("POST" if body else "GET"),
                                     headers={"Content-Type": "application/json"} if body else {})
        try:
            with self.op.open(req, timeout=30) as r:
                return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as e:
            return e.code, e.read(), {k.lower(): v for k, v in e.headers.items()}

    def json(self, path: str, data: dict | None = None, method: str | None = None):
        code, body, _ = self.raw(path, data, method)
        if code != 200:
            raise AssertionError(f"{path}: HTTP {code} {body[:200]!r}")
        return json.loads(body)


def wait_ready(base: str, seconds: int) -> None:
    v = Visitor(base)
    deadline = time.time() + seconds
    while True:
        try:
            if v.raw("/api/ready")[0] == 200:
                return
        except OSError:
            pass
        if time.time() > deadline:
            raise AssertionError(f"/api/ready не ответил 200 за {seconds} с")
        time.sleep(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--wait", type=int, default=0, help="ждать готовности до N секунд")
    ap.add_argument("--facts-as-of", default=None, help="ожидаемая дата фактов (по умолчанию из api/content.py)")
    a = ap.parse_args()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            note = fn() or ""
            results.append((name, True, note))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, f"{type(e).__name__}: {e}"))

    if a.wait:
        check("готовность", lambda: wait_ready(a.base, a.wait))
    v1, v2 = Visitor(a.base), Visitor(a.base)

    def health():
        t = time.time()
        assert v1.json("/api/health") == {"ok": True}
        return f"{(time.time() - t) * 1000:.0f} мс"

    def meta():
        expected = a.facts_as_of
        if expected is None:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            try:
                from api.content import FACTS_AS_OF as expected
            except ImportError:
                expected = None
        m = v1.json("/api/meta")
        assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", m["facts_as_of"]), m["facts_as_of"]
        assert expected is None or m["facts_as_of"] == expected, f"{m['facts_as_of']} != {expected}"
        return f"facts_as_of = {m['facts_as_of']}"

    def quote():
        q = v1.json("/api/pricing/quote", {})
        eff = q["price"]["eff_rate"]
        assert abs(eff - EXPECTED_EFF) < 5e-5, eff
        return f"эффективная ставка {eff * 100:.2f}%"

    def page():
        code, body, headers = v1.raw("/")
        assert code == 200, code
        html = body.decode("utf-8", "replace")
        js = re.search(r'src="(/assets/[^"]+\.js)"', html)
        assert js, "нет главного JS в index.html"
        code, body, _ = v1.raw(js.group(1))
        assert code == 200 and len(body) > 10_000, (code, len(body))
        assert headers.get("x-frame-options") == "DENY", headers
        return f"{js.group(1)}: {len(body) // 1024} КБ"

    def isolation():
        t0 = v1.json("/api/state")["now"]
        assert v2.json("/api/state")["now"] == t0
        v1.json("/api/clock/advance", {"days": 30})
        t1 = v1.json("/api/state")["now"]
        assert t1 != t0, "часы первого посетителя не сдвинулись"
        assert v2.json("/api/state")["now"] == t0, "«+30 дней» у первого изменил время второго"
        v2.json("/api/clock/advance", {"days": 1})
        t2 = v2.json("/api/state")["now"]
        v1.json("/api/demo/reset", {})
        assert v1.json("/api/state")["now"] == t0, "сброс не вернул часы первого"
        assert v2.json("/api/state")["now"] == t2, "сброс первого задел второго"
        v2.json("/api/demo/reset", {})
        return "часы и сброс независимы"

    for name, fn in (("/api/health", health), ("/api/meta", meta), ("/api/pricing/quote", quote),
                     ("интерфейс и JS", page), ("два посетителя", isolation)):
        check(name, fn)

    ok = all(r[1] for r in results)
    for name, good, note in results:
        print(f"{'ОК ' if good else 'ОШИБКА'}  {name}  {note}")
    print(f"\n{a.base}: {'смоук пройден' if ok else 'смоук не пройден'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
