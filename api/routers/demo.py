"""Операционное демо: счета, часы, настройки, роли."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api import services as sv
from api.deps import get_db
from api.schemas import AdvanceIn, SettingsIn
from db.models import Anchor, Event, Invoice, Supplier, SupplierAnchor
from engine import funding, lifecycle, pricing

router = APIRouter(prefix="/api", tags=["demo"])
D = Decimal


@router.get("/state")
def state(db: Session = Depends(get_db)):
    return {
        "now": sv.get_now(db),
        "scenario": sv.get_setting(db, "scenario", "M"),
        "key_rate": D(sv.get_setting(db, "key_rate", "0.14")),
        "price_mode": int(sv.get_setting(db, "price_mode", "1")),
        "mocks": {k: sv.get_setting(db, k, "0") == "1" for k in ("edo_down", "anchor_rejects", "payment_fails",
                                                                  "cfa_down")},
        "scenarios": {k: {"name": v["name"], "rate": funding.scenario_rate(k, D(sv.get_setting(db, "key_rate", "0.14"))),
                          "off_balance": funding.off_balance_share(k),
                          "weights": v["weights"]} for k, v in funding.SCENARIOS.items()},
    }


@router.put("/settings")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    if body.scenario:
        sv.set_scenario(db, body.scenario)
    if body.key_rate is not None:
        sv.set_setting(db, "key_rate", str(body.key_rate))
    if body.price_mode is not None:
        sv.set_setting(db, "price_mode", str(body.price_mode))
    for k in ("edo_down", "anchor_rejects", "payment_fails", "cfa_down"):
        v = getattr(body, k)
        if v is not None:
            sv.set_setting(db, k, "1" if v else "0")
    db.commit()
    return state(db)


@router.post("/clock/advance")
def advance(body: AdvanceIn, db: Session = Depends(get_db)):
    res = sv.advance(db, body.days, body.hours)
    db.commit()
    return res


@router.get("/invoices")
def invoices(
    db: Session = Depends(get_db),
    status: list[str] | None = Query(None),
    anchor_id: int | None = None,
    supplier_id: int | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    stmt = sv.visible(db)
    if status:
        stmt = stmt.where(Invoice.status.in_(status))
    if anchor_id:
        stmt = stmt.where(Invoice.anchor_id == anchor_id)
    if supplier_id:
        stmt = stmt.where(Invoice.supplier_id == supplier_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.join(Supplier, Supplier.id == Invoice.supplier_id).where(
            or_(Invoice.number.ilike(like), Invoice.upd_no.ilike(like), Supplier.name.ilike(like)))
    rows = db.scalars(stmt.order_by(Invoice.t_created.desc())).all()
    # Сюжетные счета для демо — наверху
    rows.sort(key=lambda i: (0 if i.story == "concentration" else
                          1 if i.status == "OFFERED" and not i.status_reason and not i.review_flag else
                          2 if i.status == "OFFERED" else 3))
    total = len(rows)
    page = rows[offset: offset + limit]
    counts = defaultdict(int)
    for r in db.scalars(sv.visible(db)).all():
        counts[r.status] += 1
    return {"total": total, "items": [sv.invoice_dict(db, i) for i in page], "status_counts": counts,
            "labels": {s.value: lifecycle.LABELS[s] for s in lifecycle.Status}}


@router.get("/invoices/{inv_id}")
def invoice(inv_id: int, db: Session = Depends(get_db)):
    return sv.invoice_dict(db, sv.get_invoice(db, inv_id), full=True)


@router.post("/invoices/{inv_id}/sell")
def sell(inv_id: int, db: Session = Depends(get_db)):
    try:
        inv = sv.sell(db, inv_id)
    except sv.ServiceError:
        db.commit()  # фиксируем запись в журнале об отказе
        raise
    db.commit()
    return sv.invoice_dict(db, inv, full=True)


@router.post("/invoices/{inv_id}/resell")
def resell(inv_id: int, db: Session = Depends(get_db)):
    res = sv.resell(db, inv_id)
    db.commit()
    if res["blocked"]:
        raise sv.Conflict(res["message"], claim_key=res["claim_key"], existing_invoice_id=res["existing_invoice_id"])
    return res


@router.post("/invoices/{inv_id}/overdue")
def overdue(inv_id: int, db: Session = Depends(get_db)):
    inv = sv.simulate_overdue(db, inv_id)
    db.commit()
    return sv.invoice_dict(db, inv, full=True)


@router.get("/events")
def events(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=500),
           invoice_id: int | None = None, kind: str | None = None):
    now = sv.get_now(db)
    stmt = select(Event).where(Event.ts <= now)
    if invoice_id:
        stmt = stmt.where(Event.invoice_id == invoice_id)
    if kind:
        stmt = stmt.where(Event.kind == kind)
    rows = db.scalars(stmt.order_by(Event.ts.desc(), Event.id.desc()).limit(limit)).all()
    return [{"id": e.id, "ts": e.ts, "kind": e.kind, "level": e.level, "message": e.message,
             "invoice_id": e.invoice_id} for e in rows]


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return sv.overview(db)


# ---------------------------------------------------------------- роли


@router.get("/suppliers")
def suppliers(db: Session = Depends(get_db)):
    offers: dict[int, int] = defaultdict(int)
    for i in db.scalars(sv.visible(db).where(Invoice.status == "OFFERED")).all():
        offers[i.supplier_id] += 1
    return [{"id": s.id, "name": s.name, "city": s.city, "revenue_mln": s.revenue_mln, "auto_sell": s.auto_sell,
             "offers": offers[s.id]} for s in sv.suppliers_list(db)]


@router.get("/suppliers/{sid}")
def supplier(sid: int, db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if not s:
        raise sv.NotFound("Поставщик не найден")
    now = sv.get_now(db)
    invs = db.scalars(sv.visible(db).where(Invoice.supplier_id == sid).order_by(Invoice.t_created.desc())).all()
    links = []
    for ln in db.scalars(select(SupplierAnchor).where(SupplierAnchor.supplier_id == sid)).all():
        used = sum(i.amount_kop for i in invs if i.anchor_id == ln.anchor_id
                   and i.status in ("SOLD", "FUNDED", "OVERDUE", "REGRESS"))
        links.append({"anchor_id": ln.anchor_id, "anchor": ln.anchor.name, "rating": ln.anchor.rating,
                      "limit": sv.rub(ln.limit_kop), "used": sv.rub(used),
                      "turnover_90d": sv.rub(ln.turnover_90d_kop), "limit_share": ln.limit_share,
                      "months_with_anchor": ln.months_with_anchor, "returns_share": ln.returns_share})
    offers = [sv.invoice_dict(db, i) for i in invs if i.status == "OFFERED"]
    hist = [sv.invoice_dict(db, i) for i in invs if i.status != "OFFERED"][:40]
    sample = next((i for i in invs if i.status == "OFFERED"), invs[0] if invs else None)
    compare = None
    if sample:
        p = sv.quote(db, sample)
        F = sv.rub(sample.amount_kop)
        k = D(sample.term_days) / D(365)
        credit = F * pricing.MSP_RATE * k
        compare = {
            "invoice": sample.number, "amount": F, "term_days": sample.term_days,
            "sell_cost": p.discount, "sell_payout": p.payout, "sell_eff_rate": p.eff_rate,
            "sell_time": "в течение суток после акцепта",
            "credit_cost": credit.quantize(D("0.01")), "credit_rate": pricing.MSP_RATE,
            "credit_time": "решение банка 3–10 рабочих дней, нужен залог или поручительство (гипотеза)",
            "difference": (p.discount - credit).quantize(D("0.01")),
            "note": "Кредит МСП в среднем дешевле, но требует залога и времени на одобрение. Продажа счёта "
                    "не увеличивает долговую нагрузку поставщика.",
        }
    timeline = []
    funded = [i for i in invs if i.funded_at and i.accepted_at][:12]
    for i in funded:
        timeline.append({"number": i.number, "accepted_at": i.accepted_at, "funded_at": i.funded_at,
                         "hours": round((i.funded_at - i.accepted_at).total_seconds() / 3600, 1)})
    return {"supplier": {"id": s.id, "name": s.name, "city": s.city, "revenue_mln": s.revenue_mln,
                         "auto_sell": s.auto_sell},
            "now": now, "links": links, "offers": offers, "history": hist, "compare": compare,
            "timeline": timeline}


@router.get("/anchors")
def anchors(db: Session = Depends(get_db)):
    return [{"id": a.id, "name": a.name, "industry": a.industry, "rating": a.rating} for a in sv.anchors_list(db)]


@router.get("/anchors/{aid}")
def anchor(aid: int, db: Session = Depends(get_db)):
    from engine.scoring import AnchorMetrics, score_anchor

    a = db.get(Anchor, aid)
    if not a:
        raise sv.NotFound("Якорь не найден")
    now = sv.get_now(db)
    invs = db.scalars(sv.visible(db).where(Invoice.anchor_id == aid).order_by(Invoice.t_created.desc())).all()
    acceptances = [sv.invoice_dict(db, i) for i in invs if i.accepted_at][:60]
    cal: dict[str, dict] = {}
    for i in invs:
        if i.status in ("FUNDED", "SOLD", "OVERDUE") and i.due_date <= (now + timedelta(days=90)).date():
            key = i.due_date.isoformat()
            c = cal.setdefault(key, {"date": i.due_date, "amount": D(0), "count": 0, "overdue": 0})
            c["amount"] += sv.rub(i.amount_kop)
            c["count"] += 1
            if i.status == "OVERDUE":
                c["overdue"] += 1
    sup: dict[int, dict] = {}
    for i in invs:
        r = sup.setdefault(i.supplier_id, {"supplier_id": i.supplier_id, "name": i.supplier.name,
                                           "turnover": D(0), "count": 0, "overdue": 0})
        r["turnover"] += sv.rub(i.amount_kop)
        r["count"] += 1
        if i.pay_delay_days or i.defaults:
            r["overdue"] += 1
    ov = sv.overview(db)
    mine = next(x for x in ov["by_anchor"] if x["anchor_id"] == aid)
    sc = score_anchor(AnchorMetrics(D(str(a.debt_to_ebitda)), a.avg_payment_delay_days,
                                    D(str(a.rejected_acceptance_share)), a.business_age_years))
    return {
        "anchor": {"id": a.id, "name": a.name, "industry": a.industry, "rating": a.rating, "points": a.score_points,
                   "pd": pricing.RATING_PD[a.rating], "term_min": a.term_min, "term_max": a.term_max,
                   "default_term_days": a.default_term_days, "limit": sv.rub(a.limit_kop),
                   "supplier_sublimit": sv.rub(a.supplier_sublimit_kop)},
        "scoring": {"points": sc.points, "rating": sc.rating, "rules": sc.rules},
        "now": now,
        "acceptances": acceptances,
        "calendar": sorted(cal.values(), key=lambda x: x["date"]),
        "suppliers": sorted(sup.values(), key=lambda x: -x["turnover"])[:15],
        "portfolio": mine,
        "anchor_cap": ov["anchor_cap"],
    }


@router.get("/investor")
def investor(db: Session = Depends(get_db), cover: Decimal = Query(D(0), ge=0, le=D("0.8")),
             ins_rate: Decimal = Query(D("0.01"), ge=0, le=D("0.1"))):
    now = sv.get_now(db)
    lgd = D("0.6")
    invs = db.scalars(sv.visible(db).where(Invoice.funding_source.in_(["cfa", "treasury", "syndication"]),
                                           Invoice.funded_at.is_not(None))).all()
    key_rate = D(sv.get_setting(db, "key_rate", "0.14"))
    tranches: dict[str, dict] = {}
    for i in invs:
        src = i.funding_source
        tid = f"{i.funded_at:%Y-%m}-{src}"
        t = tranches.setdefault(tid, {"id": tid, "month": f"{i.funded_at:%Y-%m}", "source": src,
                                      "source_name": funding.source_name(src), "amount": D(0), "count": 0,
                                      "outstanding": D(0), "repaid": D(0), "overdue": D(0), "wavg_days": D(0),
                                      "yield": key_rate + pricing.FUNDING_SOURCES[src]["premium"],
                                      "el": D(0), "anchors": defaultdict(lambda: D(0))})
        amt = sv.rub(i.amount_kop)
        t["amount"] += amt
        t["count"] += 1
        t["wavg_days"] += amt * i.term_days
        if i.status in ("FUNDED", "SOLD"):
            t["outstanding"] += amt
        elif i.status in ("OVERDUE", "REGRESS"):
            t["overdue"] += amt
            t["outstanding"] += amt
        else:
            t["repaid"] += amt
        t["el"] += amt * pricing.RATING_PD[i.anchor.rating] * lgd * (1 - cover) * D(i.term_days) / D(365)
        t["anchors"][i.anchor.name] += amt
    out = []
    for t in sorted(tranches.values(), key=lambda x: x["id"], reverse=True):
        t["wavg_days"] = t["wavg_days"] / t["amount"] if t["amount"] else D(0)
        top = max(t["anchors"].items(), key=lambda kv: kv[1]) if t["anchors"] else ("", D(0))
        t["top_anchor"] = top[0]
        t["top_anchor_share"] = top[1] / t["amount"] if t["amount"] else D(0)
        t["net_yield"] = t["yield"] - cover * ins_rate
        t["anchors"] = dict(t["anchors"])
        t["issuer"] = "SPV-эмитент (модельный)"
        out.append(t)
    total = sum((t["amount"] for t in out), D(0))
    outstanding = sum((t["outstanding"] for t in out), D(0))
    conc: dict[str, D] = defaultdict(lambda: D(0))
    for i in invs:
        if i.status in ("FUNDED", "SOLD", "OVERDUE", "REGRESS"):
            conc[i.anchor.name] += sv.rub(i.amount_kop)
    el_total = sum((t["el"] for t in out), D(0))
    return {
        "now": now, "cover": cover, "ins_rate": ins_rate, "tranches": out[:30], "total_issued": total,
        "outstanding": outstanding, "expected_loss": el_total,
        "expected_loss_no_cover": el_total / (1 - cover) if cover < 1 else el_total,
        "concentration": sorted([{"anchor": k, "amount": v, "share": (v / outstanding if outstanding else D(0))}
                                 for k, v in conc.items()], key=lambda x: -x["amount"]),
        "legal_note": "Инвестор получает требование к эмитенту (модельному SPV), а не к якорю. Риск якоря доходит "
                      "до инвестора только через обеспечение или страхование; доля покрытия задаётся параметром.",
    }
