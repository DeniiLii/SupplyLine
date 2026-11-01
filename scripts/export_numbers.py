"""Единый источник чисел для презентации, видео, аналитики и текста формы: deliverables/numbers.json.

Запуск: python scripts/export_numbers.py [--out deliverables/numbers.json]
Считает финмодель (база, сценарии, стресс при 25% и 15%, рычаги), симулятор по умолчанию, обзор демо-портфеля
из свежего сида (отдельная временная БД), оценку рынка снизу вверх и число тестов. Детерминирован: seed 42.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Своя БД до импорта приложения: экспорт не трогает рабочую базу
os.environ["SUPPLYLINE_DB"] = str(Path(tempfile.mkdtemp(prefix="sl-numbers-")) / "numbers.sqlite3")
os.environ["SUPPLYLINE_MOCK_LATENCY"] = "0"
os.environ["SUPPLYLINE_SANDBOX"] = "0"

D = Decimal

# Оценка рынка снизу вверх: SAM = N × a × R × b (docs/analytics/02_market_estimate.md, раздел 3). Гипотезы автора
MARKET_SCENARIOS = {
    "low": {"a": D("0.20"), "R_bn": D("1.2"), "b": D("0.20")},
    "base": {"a": D("0.30"), "R_bn": D("1.3"), "b": D("0.30")},
    "high": {"a": D("0.40"), "R_bn": D("1.4"), "b": D("0.40")},
}
MARKET_FACTS = {
    "factoring_portfolio_bn_2026_07_01": D(2791),
    "factoring_active_clients_h1_2026": 15626,
    "factoring_turnover_bn_2025_unverified": D(10252),
}


def num(x, nd: int = 6):
    if isinstance(x, Decimal):
        return round(float(x), nd)
    if isinstance(x, float):
        return round(x, nd)
    return x


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return num(o)


def finmodel() -> dict:
    from api.routers.finmodel import levers
    from engine.finmodel import FinParams, cap_credit, run

    p = FinParams()
    base = run(p)
    k, st = base["kpis"], base["stress"]
    st15 = run(FinParams(stress_share=D("0.15")))["stress"]
    years = [{key: y[key] for key in ("year", "turnover_bn", "income", "pbt", "np", "cum_np", "bal_end", "eff",
                                      "fix_opex", "suppliers", "anchors")} for y in base["years"]]
    matrix = {f"{m['scenario']}{m['mode']}": {"np5": m["np5"], "cum_np5": m["cum_np5"], "eff5": m["eff5"],
                                               "eq_need": m["eq_need"], "verdict": m["verdict"]}
              for m in base["matrix"]}
    sens = {r["key"]: {"name": r["name"], "range_half": r["range"] / 2, "delta_low": r["delta_low"],
                       "delta_high": r["delta_high"]} for r in base["sensitivity"]["rows"]}

    def stress(s):
        return {k2: s[k2] for k2 in ("share", "month", "loss", "capital", "coverage", "max_share", "covered")}

    return {
        "params": {"ks": p.ks_now, "t_days": p.t_days, "lgd": p.lgd, "r_opex": p.r_opex, "r_margin": p.r_margin,
                   "msp_rate": p.msp_rate, "speed_prem": p.speed_prem, "cap_rate": cap_credit(p), "tax": p.tax},
        "years": years,
        "kpis": {key: k[key] for key in ("payback_month", "cum_np_5y", "cum_np_bottom", "cum_np_bottom_month",
                                         "first_positive_np_month", "eq_need_peak", "eq_need_peak_month",
                                         "breakeven_turnover_y5", "breakeven_share_y5")},
        "matrix": matrix,
        "sensitivity_pbt5": {"base_pbt": base["sensitivity"]["base_pbt"], "rows": sens},
        "stress_book_25": stress(st),
        "stress_platform_15": stress(st15),
        "checks_ok": all(c["ok"] for c in base["checks"]),
        "checks_count": len(base["checks"]),
        "levers": [{key: x[key] for key in x if key != "cum_np"} for x in levers()["presets"]],
    }


def market(fm: dict) -> dict:
    from engine.finmodel import FinParams

    p = FinParams()
    y5 = fm["years"][4]
    plan_turnover = D(str(y5["turnover_bn"]))
    out = {"N": p.market_mid_companies, "plan_y5": {"turnover_bn": plan_turnover, "suppliers": y5["suppliers"],
                                                     "anchors": y5["anchors"], "bal_end_mln": y5["bal_end"]},
           "facts": MARKET_FACTS, "scenarios": {}}
    for key, s in MARKET_SCENARIOS.items():
        firms = D(p.market_mid_companies) * s["a"]
        sam = firms * s["R_bn"] * s["b"]
        out["scenarios"][key] = {**s, "firms": firms, "sam_bn": sam, "plan_share": plan_turnover / sam,
                                 "coverage": D(y5["suppliers"]) / firms}
    out["turnover_per_supplier_mln"] = plan_turnover * 1000 / y5["suppliers"]
    out["turnover_per_anchor_bn"] = plan_turnover / y5["anchors"]
    out["plan_vs_factoring_turnover"] = plan_turnover / MARKET_FACTS["factoring_turnover_bn_2025_unverified"]
    out["bal_vs_factoring_portfolio"] = D(str(y5["bal_end"])) / 1000 / MARKET_FACTS["factoring_portfolio_bn_2026_07_01"]
    out["suppliers_vs_active_clients"] = D(y5["suppliers"]) / MARKET_FACTS["factoring_active_clients_h1_2026"]
    return out


def demo() -> dict:
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        c.post("/api/demo/reset")
        q = c.post("/api/pricing/quote", json={}).json()
        ov = c.get("/api/overview").json()
        st = c.get("/api/state").json()
        meta = c.get("/api/meta").json()
    return {
        "simulator_default": {"eff_rate": q["price"]["eff_rate"], "r_total": q["price"]["r_total"],
                              "msp_rate": q["compare"]["msp_rate"],
                              "over_msp_pp": (q["price"]["eff_rate"] - q["compare"]["msp_rate"]) * 100,
                              "components": {w["key"]: w["rate"] for w in q["waterfall"]}},
        "overview": {**{k: ov["kpi"][k] for k in ("duplicates_blocked", "invoices_visible", "outstanding",
                                                  "turnover_total", "overdue30_share", "off_balance_share")},
                     "gates": {g["key"]: {"value": g["value"], "ok": g["ok"]} for g in ov["gates"]}},
        "anchor_cap": st["anchor_cap"],
        "program_size": ov["program_size"],
        "facts_as_of": meta["facts_as_of"],
        "facts_count": len(meta["facts"]),
        "seed": {"anchors": 5, "suppliers": 40},
    }


def tests() -> dict:
    def collect(args: list[str]) -> int:
        r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", *args], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        for line in reversed(r.stdout.splitlines()):
            if "collected" in line or "tests" in line:
                return int(line.split()[0].split("/")[0])
        return 0

    return {"unit": collect([]), "e2e": collect(["-m", "e2e"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "deliverables" / "numbers.json"))
    a = ap.parse_args()
    fm = finmodel()
    data = {"generated": date.today().isoformat(), "seed": 42, "finmodel": fm, "market": market(fm),
            "demo": demo(), "tests": tests(), "video": video()}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clean(data), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out}: {out.stat().st_size // 1024} КБ")


def video() -> dict:
    mp4 = ROOT / "deliverables" / "SupplyLine_demo.mp4"
    if not mp4.exists():
        return {}
    sys.path.insert(0, str(ROOT / "scripts"))
    from record_demo import duration

    return {"seconds": duration(mp4), "mb": mp4.stat().st_size / 1e6}


if __name__ == "__main__":
    main()
