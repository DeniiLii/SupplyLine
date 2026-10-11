"""Операции демо поверх БД: продажа счёта, реестр, лимиты, часы, просрочка, агрегаты.

Расчёт цены — только engine.pricing; здесь нет собственных формул цены.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from adapters import mocks
from adapters.ports import PortError
from db.models import Anchor, Event, Invoice, RegistryEntry, Setting, Supplier, SupplierAnchor
from engine import funding, lifecycle, pricing, registry
from engine.lifecycle import FINANCED, Status
from engine.portfolio import ANCHOR_CAP, INDUSTRY_CAP, PROGRAM_SIZE, Exposure, check_limits, first_failed

D = Decimal
ST = Status


# ---------------------------------------------------------------- ошибки


class ServiceError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra


class NotFound(ServiceError):
    status_code = 404
    code = "not_found"


class Conflict(ServiceError):
    status_code = 409
    code = "conflict"


class LimitBlocked(ServiceError):
    status_code = 422
    code = "limit_blocked"


class ExternalFailure(ServiceError):
    status_code = 503
    code = "external_failure"


# ---------------------------------------------------------------- настройки и журнал


def get_setting(s: Session, key: str, default: str | None = None) -> str | None:
    row = s.get(Setting, key)
    return row.value if row else default


def set_setting(s: Session, key: str, value: str) -> None:
    row = s.get(Setting, key)
    if row:
        row.value = value
    else:
        s.add(Setting(key=key, value=value))


def get_now(s: Session) -> datetime:
    return datetime.fromisoformat(get_setting(s, "now"))


def sync_mock_config(s: Session) -> None:
    for k in ("edo_down", "anchor_rejects", "payment_fails", "cfa_down"):
        setattr(mocks.CONFIG, k, get_setting(s, k, "0") == "1")


def log(s: Session, ts: datetime, kind: str, message: str, invoice_id: int | None = None,
        level: str = "info", data: dict | None = None) -> None:
    s.add(Event(ts=ts, kind=kind, message=message, invoice_id=invoice_id, level=level, data=data))


def count_events(s: Session) -> int:
    return s.scalar(select(func.count(Event.id))) or 0


def rub(kop: int) -> Decimal:
    return D(kop) / 100


# ---------------------------------------------------------------- цена


def price_params(s: Session) -> dict:
    return {
        "key_rate": D(get_setting(s, "key_rate", "0.14")),
        "scenario": get_setting(s, "scenario", "M"),
        "mode": int(get_setting(s, "price_mode", "1")),
    }


def quote(s: Session, inv: Invoice) -> pricing.Price:
    pp = price_params(s)
    r_fund = funding.scenario_rate(pp["scenario"], pp["key_rate"])
    return pricing.price(pricing.PriceInput(
        face=rub(inv.amount_kop), t_days=inv.term_days, r_fund=r_fund,
        pd=pricing.RATING_PD[inv.anchor.rating], mode=pp["mode"],
    ))


def explain_price(s: Session, inv: Invoice) -> dict:
    """Блок «Почему такая цена»: сработавшие правила скоринга якоря и состав ставки."""
    from engine.scoring import AnchorMetrics, score_anchor

    a = inv.anchor
    sc = score_anchor(AnchorMetrics(D(str(a.debt_to_ebitda)), a.avg_payment_delay_days,
                                    D(str(a.rejected_acceptance_share)), a.business_age_years))
    pp = price_params(s)
    sc_info = funding.SCENARIOS[pp["scenario"]]
    return {
        "anchor_rating": sc.rating,
        "anchor_points": sc.points,
        "pd": sc.pd,
        "rules": sc.rules,
        "funding_scenario": pp["scenario"],
        "funding_scenario_name": sc_info["name"],
        "funding_weights": sc_info["weights"],
        "key_rate": pp["key_rate"],
        "r_fund": funding.scenario_rate(pp["scenario"], pp["key_rate"]),
        "note": "Цена зависит от риска якоря, а не поставщика. Скоринг поставщика влияет только на лимит.",
    }


def _apply_price(inv: Invoice, p: pricing.Price, r_fund: Decimal) -> None:
    inv.r_total = float(p.r_total)
    inv.r_fund = float(r_fund)
    inv.discount_kop = int(p.discount * 100)
    inv.payout_kop = int(p.payout * 100)
    inv.spread_kop = int(p.spread * 100)


# ---------------------------------------------------------------- переходы


def _move(s: Session, inv: Invoice, dst: Status, ts: datetime, message: str, level: str = "info",
          data: dict | None = None) -> None:
    src = inv.status
    inv.status = lifecycle.transition(src, dst).value
    log(s, ts, "transition", message, inv.id, level,
        {"from": src, "to": dst.value, **(data or {})})


def _claim(inv: Invoice) -> str:
    return registry.claim_key(inv.anchor_id, inv.supplier_id, inv.upd_no, inv.upd_date, rub(inv.amount_kop))


def _book(s: Session, exclude_id: int | None = None) -> list[Exposure]:
    rows = s.execute(
        select(Invoice.id, Invoice.anchor_id, Invoice.supplier_id, Anchor.industry_code, Invoice.amount_kop)
        .join(Anchor, Anchor.id == Invoice.anchor_id)
        .where(Invoice.status.in_([x.value for x in (ST.SOLD, *FINANCED)]))
    ).all()
    return [Exposure(a, sp, ind, rub(k)) for i, a, sp, ind, k in rows if i != exclude_id]


def limit_checks(s: Session, inv: Invoice) -> list:
    link = s.get(SupplierAnchor, (inv.supplier_id, inv.anchor_id))
    sup_limit = rub(link.limit_kop) if link else D(0)
    prog = D(get_setting(s, "program_size", str(PROGRAM_SIZE)))
    return check_limits(
        new=Exposure(inv.anchor_id, inv.supplier_id, inv.anchor.industry_code, rub(inv.amount_kop)),
        book=_book(s, inv.id), anchor_limit=rub(inv.anchor.limit_kop), supplier_limit_value=sup_limit,
        program_size=prog,
    )


def _similar(s: Session, inv: Invoice) -> list[Invoice]:
    rows = s.scalars(
        select(Invoice).join(RegistryEntry, RegistryEntry.invoice_id == Invoice.id)
        .where(Invoice.anchor_id == inv.anchor_id, Invoice.supplier_id == inv.supplier_id,
               Invoice.id != inv.id)
    ).all()
    me = registry.ClaimView(inv.id, inv.anchor_id, inv.supplier_id, inv.upd_no, inv.upd_date, rub(inv.amount_kop))
    out = []
    for r in rows:
        v = registry.ClaimView(r.id, r.anchor_id, r.supplier_id, r.upd_no, r.upd_date, rub(r.amount_kop))
        if registry.is_similar(me, v):
            out.append(r)
    return out


def _offer(s: Session, inv: Invoice, ts: datetime) -> None:
    sim = _similar(s, inv)
    if sim:
        inv.review_flag = True
        inv.review_reason = (f"Похож на счёт {sim[0].number}: тот же якорь и поставщик, сумма в пределах 1%, "
                             f"дата в пределах 3 дней. Автопокупка заблокирована до ручной проверки.")
        log(s, ts, "review", f"{inv.number}: отправлен на проверку как похожий на {sim[0].number}",
            inv.id, "warning", {"similar_to": sim[0].id})
        return
    pp = price_params(s)
    p = quote(s, inv)
    _apply_price(inv, p, funding.scenario_rate(pp["scenario"], pp["key_rate"]))
    _move(s, inv, ST.OFFERED, ts, f"{inv.number}: предложение {_fmt_pct(p.r_total)} годовых, "
          f"к выплате {_fmt_rub(p.payout)}")


def _sell(s: Session, inv: Invoice, ts: datetime, manual: bool) -> None:
    if inv.status != ST.OFFERED.value:
        raise Conflict(f"Продать можно только счёт в статусе «Предложение», сейчас «{lifecycle.LABELS[ST(inv.status)]}»")
    if inv.review_flag:
        raise Conflict("Счёт на ручной проверке как похожий на уже профинансированный")
    checks = limit_checks(s, inv)
    bad = first_failed(checks)
    if bad:
        inv.status_reason = f"Сработало правило «{bad.rule}»: {_fmt_rub(bad.used)} при лимите {_fmt_rub(bad.limit)}"
        log(s, ts, "limit_blocked", f"{inv.number}: покупка заблокирована. {inv.status_reason}", inv.id,
            "warning", {"rule": bad.rule, "used": float(bad.used), "limit": float(bad.limit)})
        raise LimitBlocked(inv.status_reason, rule=bad.rule, checks=[c.as_dict() for c in checks])
    key = _claim(inv)
    try:
        with s.begin_nested():
            s.add(RegistryEntry(claim_key=key, invoice_id=inv.id, created_at=ts, holder="SPV-эмитент"))
            s.flush()
    except IntegrityError:
        existing = s.scalar(select(RegistryEntry).where(RegistryEntry.claim_key == key))
        log(s, ts, "duplicate_blocked", f"{inv.number}: требование уже в реестре, продажа заблокирована",
            inv.id, "danger", {"claim_key": key})
        raise Conflict("Требование уже есть в реестре: двойное финансирование заблокировано",
                       claim_key=key, existing_invoice_id=existing.invoice_id if existing else None) from None
    if manual:
        sync_mock_config(s)
        res = mocks.payment.payout(inv.id, rub(inv.payout_kop or 0))
        if not res.ok:
            s.query(RegistryEntry).filter(RegistryEntry.claim_key == key).delete()
            log(s, ts, "payment_failed", f"{inv.number}: {res.reason}", inv.id, "danger")
            raise ExternalFailure(f"{res.reason}. Повторите позже: требование не уступлено.")
    sc = get_setting(s, "scenario", "M")
    inv.funding_source = funding.allocate(sc, inv.id)
    if inv.funding_source == "cfa" and manual:
        try:
            mocks.cfa.issue(f"T{inv.id}", rub(inv.amount_kop))
        except PortError as e:
            log(s, ts, "cfa_fallback", f"{inv.number}: {e}. Счёт профинансирован с баланса.", inv.id, "warning")
            inv.funding_source = "bank"
    inv.t_sold = ts
    _move(s, inv, ST.SOLD, ts, f"{inv.number}: требование уступлено ({funding.source_name(inv.funding_source)})",
          data={"source": inv.funding_source})
    if manual:
        # Деньги приходят в течение суток: детерминированная задержка 2–20 ч
        h = 2 + int(hashlib.sha1(str(inv.id).encode()).hexdigest(), 16) % 18
        inv.t_funded = ts + timedelta(hours=h)
        inv.plan = "manual_sold"


def _fmt_rub(x: Decimal) -> str:
    return f"{x:,.0f}".replace(",", " ") + " ₽"


def _fmt_pct(x: Decimal) -> str:
    return f"{x * 100:.2f}".replace(".", ",") + "%"


# ---------------------------------------------------------------- часы


def process_until(s: Session, now: datetime, quiet_latency: bool = False) -> int:
    """Проигрывает запланированные события всех счетов до момента now."""
    moved = 0
    invs = s.scalars(
        select(Invoice).where(Invoice.t_created <= now,
                              Invoice.status.notin_([x.value for x in lifecycle.TERMINAL]))
        .order_by(Invoice.t_created)
    ).all()
    # Сначала события в хронологическом порядке (важно для лимитов и реестра)
    for inv in invs:
        moved += _advance_invoice(s, inv, now)
    s.flush()
    return moved


def _advance_invoice(s: Session, inv: Invoice, now: datetime) -> int:
    n = 0
    for _ in range(12):
        st = ST(inv.status)
        before = inv.status
        if st == ST.DRAFT:
            if inv.t_created <= now and inv.t_upd and inv.t_upd <= now:
                if inv.plan == "edo_fail":
                    inv.status_reason = "ЭДО: УПД с такими реквизитами не найден у оператора"
                    _move(s, inv, ST.REJECTED, inv.t_upd, f"{inv.number}: {inv.status_reason}", "danger")
                else:
                    _move(s, inv, ST.UPD_VERIFIED, inv.t_upd, f"{inv.number}: УПД найден в ЭДО")
        elif st == ST.UPD_VERIFIED:
            if inv.t_accept and inv.t_accept <= now:
                if inv.plan == "reject":
                    inv.status_reason = "Якорь отклонил акцепт: расхождение по количеству товара"
                    _move(s, inv, ST.REJECTED, inv.t_accept, f"{inv.number}: {inv.status_reason}", "warning")
                else:
                    inv.accepted_at = inv.t_accept
                    _move(s, inv, ST.ACCEPTED, inv.t_accept, f"{inv.number}: якорь акцептовал обязательство")
        elif st == ST.ACCEPTED:
            if not inv.review_flag:
                _offer(s, inv, inv.accepted_at or inv.t_accept)
        elif st == ST.OFFERED:
            if inv.plan == "auto" and inv.t_sold and inv.t_sold <= now:
                try:
                    _sell(s, inv, inv.t_sold, manual=False)
                except ServiceError:
                    inv.plan = "manual"
            elif inv.plan == "manual" and inv.story != "concentration" and inv.accepted_at and \
                    now - inv.accepted_at > timedelta(days=14):
                inv.status_reason = "Предложение не принято за 14 дней"
                _move(s, inv, ST.EXPIRED, inv.accepted_at + timedelta(days=14),
                      f"{inv.number}: предложение истекло")
        elif st == ST.SOLD:
            if inv.t_funded and inv.t_funded <= now:
                inv.funded_at = inv.t_funded
                hours = (inv.funded_at - (inv.accepted_at or inv.funded_at)).total_seconds() / 3600
                _move(s, inv, ST.FUNDED, inv.t_funded,
                      f"{inv.number}: поставщик получил {_fmt_rub(rub(inv.payout_kop or 0))}",
                      data={"hours_from_accept": round(hours, 1)})
        elif st == ST.FUNDED:
            due = _dt(inv.due_date)
            if inv.story == "dup_attempt" and inv.funded_at and inv.funded_at + timedelta(days=1) <= now:
                _dup_attempt(s, inv, inv.funded_at + timedelta(days=1))
                inv.story = "dup_attempted"
            if due <= now:
                if inv.pay_delay_days == 0 and not inv.defaults:
                    inv.repaid_at = due
                    _move(s, inv, ST.REPAID, due, f"{inv.number}: якорь оплатил в срок, требование закрыто")
                else:
                    inv.overdue_since = inv.due_date
                    _move(s, inv, ST.OVERDUE, due, f"{inv.number}: якорь не оплатил в срок, отправлено напоминание",
                          "warning")
        elif st == ST.OVERDUE:
            due = _dt(inv.due_date)
            if not inv.defaults and due + timedelta(days=inv.pay_delay_days) <= now:
                t = due + timedelta(days=inv.pay_delay_days)
                inv.repaid_at = t
                _move(s, inv, ST.REPAID, t, f"{inv.number}: якорь оплатил с опозданием {inv.pay_delay_days} дн.")
            elif inv.defaults and due + timedelta(days=30) <= now:
                _move(s, inv, ST.REGRESS, due + timedelta(days=30),
                      f"{inv.number}: просрочка 30 дней, предъявлен регресс поставщику по договору", "danger")
        elif st == ST.REGRESS:
            due = _dt(inv.due_date)
            if due + timedelta(days=75) <= now:
                inv.repaid_at = due + timedelta(days=75)
                _move(s, inv, ST.RECOVERED, due + timedelta(days=75),
                      f"{inv.number}: поставщик погасил требование по регрессу")
        if inv.status == before:
            break
        n += 1
    return n


def _dt(d_: date) -> datetime:
    return datetime(d_.year, d_.month, d_.day)


def _dup_attempt(s: Session, inv: Invoice, ts: datetime) -> dict:
    key = _claim(inv)
    try:
        with s.begin_nested():
            s.add(RegistryEntry(claim_key=key, invoice_id=inv.id, created_at=ts, holder="повторная заявка"))
            s.flush()
    except IntegrityError:
        existing = s.scalar(select(RegistryEntry).where(RegistryEntry.claim_key == key))
        msg = (f"{inv.number}: повторная продажа того же требования заблокирована реестром "
               f"(ключ {key[:12]}…)")
        log(s, ts, "duplicate_blocked", msg, inv.id, "danger", {"claim_key": key})
        return {"blocked": True, "claim_key": key,
                "existing_invoice_id": existing.invoice_id if existing else None, "message": msg}
    # Требования в реестре нет (счёт не продавался) — откатываем пробную запись
    s.query(RegistryEntry).filter(RegistryEntry.claim_key == key, RegistryEntry.holder == "повторная заявка").delete()
    return {"blocked": False, "claim_key": key, "message": "Требования нет в реестре"}


def advance(s: Session, days: int = 0, hours: int = 0) -> dict:
    from engine.clock import advance as adv

    before = get_now(s)
    now = adv(before, days, hours)
    set_setting(s, "now", now.isoformat())
    moved = process_until(s, now)
    log(s, now, "clock", f"Часы переведены на {days} дн. вперёд" if days else f"Часы +{hours} ч")
    return {"from": before, "to": now, "transitions": moved}


def tune_concentration_story(s: Session) -> None:
    """Подбирает плановый размер программы так, чтобы сюжетный крупный счёт упирался
    в потолок концентрации 25%, а обычные счета якоря проходили."""
    big = s.scalar(select(Invoice).where(Invoice.story == "concentration"))
    if not big:
        return
    book = _book(s)
    # Поставщик с наибольшим запасом по лимиту, чтобы первым срабатывал именно потолок концентрации
    links = s.scalars(select(SupplierAnchor).where(SupplierAnchor.anchor_id == big.anchor_id)).all()
    used = {ln.supplier_id: sum((e.amount for e in book if e.anchor_id == big.anchor_id
                                 and e.supplier_id == ln.supplier_id), D(0)) for ln in links}
    best = max(links, key=lambda ln: rub(ln.limit_kop) - used[ln.supplier_id])
    big.supplier_id = best.supplier_id
    need = used[best.supplier_id] + rub(big.amount_kop) + D(5_000_000)
    if rub(best.limit_kop) < need:
        best.limit_kop = int(need * 100)
    x = sum((e.amount for e in book if e.anchor_id == big.anchor_id), D(0))
    total = sum((e.amount for e in book), D(0))
    amt = rub(big.amount_kop)
    program = max((x + amt - D(5_000_000)) / ANCHOR_CAP, total + amt)
    set_setting(s, "program_size", str(program.quantize(D(1))))


# ---------------------------------------------------------------- действия пользователя


def get_invoice(s: Session, inv_id: int) -> Invoice:
    inv = s.get(Invoice, inv_id)
    if not inv or inv.t_created > get_now(s):
        raise NotFound("Счёт не найден")
    return inv


def sell(s: Session, inv_id: int) -> Invoice:
    inv = get_invoice(s, inv_id)
    _sell(s, inv, get_now(s), manual=True)
    return inv


def resell(s: Session, inv_id: int) -> dict:
    inv = get_invoice(s, inv_id)
    return _dup_attempt(s, inv, get_now(s))


def simulate_overdue(s: Session, inv_id: int) -> Invoice:
    inv = get_invoice(s, inv_id)
    if inv.status not in (ST.FUNDED.value, ST.SOLD.value):
        raise Conflict("Просрочку можно смоделировать только для профинансированного счёта")
    now = get_now(s)
    inv.defaults = True
    inv.pay_delay_days = 0
    log(s, now, "scenario", f"{inv.number}: смоделирован неплатёж якоря в срок оплаты", inv.id, "warning")
    if inv.status == ST.FUNDED.value and _dt(inv.due_date) > now:
        # Сдвигаем срок оплаты на «сегодня», чтобы неплатёж был виден сразу
        inv.due_date = now.date()
    process_until(s, now)
    return inv


def set_scenario(s: Session, code: str) -> None:
    if code not in funding.SCENARIOS:
        raise ServiceError("Сценарий фондирования должен быть A, B, C или M")
    set_setting(s, "scenario", code)
    log(s, get_now(s), "settings", f"Сценарий фондирования: {code} «{funding.SCENARIOS[code]['name']}»")


# ---------------------------------------------------------------- агрегаты


def visible(s: Session):
    return select(Invoice).where(Invoice.t_created <= get_now(s))


def overview(s: Session) -> dict:
    now = get_now(s)
    invs = s.scalars(visible(s)).all()
    anchors = {a.id: a for a in s.scalars(select(Anchor)).all()}
    funded_like = [i for i in invs if i.funded_at]
    outstanding = [i for i in invs if i.status in {x.value for x in FINANCED}]
    out_amt = sum(i.amount_kop for i in outstanding)
    last30 = [i for i in funded_like if i.funded_at > now - timedelta(days=30)]
    turnover_30 = sum(i.amount_kop for i in last30)
    spread_30 = sum(i.spread_kop or 0 for i in last30)
    overdue30 = [i for i in outstanding if i.overdue_since and (now.date() - i.overdue_since).days >= 30]
    off = sum(i.amount_kop for i in outstanding
              if i.funding_source and not pricing.FUNDING_SOURCES[i.funding_source]["on_balance"])
    by_month: dict[str, int] = defaultdict(int)
    for i in funded_like:
        by_month[i.funded_at.strftime("%Y-%m")] += i.amount_kop
    by_anchor = []
    prog = D(get_setting(s, "program_size", str(PROGRAM_SIZE)))
    base = max(rub(out_amt), prog)
    for a in anchors.values():
        amt = sum(i.amount_kop for i in outstanding if i.anchor_id == a.id)
        by_anchor.append({"anchor_id": a.id, "name": a.name, "rating": a.rating, "industry": a.industry,
                          "outstanding": rub(amt), "share": (rub(amt) / base) if base else D(0),
                          "limit": rub(a.limit_kop), "cap": ANCHOR_CAP * base})
    by_source: dict[str, int] = defaultdict(int)
    for i in outstanding:
        by_source[i.funding_source or "bank"] += i.amount_kop
    funnel_order = ["DRAFT", "UPD_VERIFIED", "ACCEPTED", "OFFERED", "SOLD", "FUNDED", "REPAID"]
    # Воронка: сколько счетов дошли хотя бы до этапа. Просрочка и регресс считаются этапом «Профинансирован»;
    # отклонённые и истёкшие учитываются по последнему достигнутому этапу.
    rank = {k: n for n, k in enumerate(funnel_order)}
    after_funding = {"OVERDUE": rank["FUNDED"], "REGRESS": rank["FUNDED"], "RECOVERED": rank["FUNDED"],
                     "WRITTEN_OFF": rank["FUNDED"]}
    reached = Counter()
    for i in invs:
        if i.status in rank:
            top = rank[i.status]
        elif i.status in after_funding:
            top = after_funding[i.status]
        elif i.accepted_at:
            top = rank["OFFERED"] if i.r_total is not None else rank["ACCEPTED"]
        elif i.plan == "reject":
            top = rank["UPD_VERIFIED"]
        else:
            top = rank["DRAFT"]
        for k, n in rank.items():
            if n <= top:
                reached[k] += 1
    stages = [{"stage": k, "label": lifecycle.LABELS[ST(k)], "count": reached[k]} for k in funnel_order]
    status_counts = Counter(i.status for i in invs)
    blocked = s.scalar(select(func.count(Event.id)).where(Event.kind == "duplicate_blocked",
                                                         Event.ts <= now)) or 0
    return {
        "now": now,
        "scenario": get_setting(s, "scenario", "M"),
        "kpi": {
            "turnover_total": rub(sum(i.amount_kop for i in funded_like)),
            "turnover_30d": rub(turnover_30),
            "outstanding": rub(out_amt),
            "spread_30d": rub(spread_30),
            "overdue30_share": (D(sum(i.amount_kop for i in overdue30)) / out_amt) if out_amt else D(0),
            "overdue30_amount": rub(sum(i.amount_kop for i in overdue30)),
            "off_balance_share": (D(off) / out_amt) if out_amt else D(0),
            "fraud_losses": D(0),
            "duplicates_blocked": blocked,
            "invoices_visible": len(invs),
        },
        "turnover_by_month": [{"month": k, "amount": rub(v)} for k, v in sorted(by_month.items())],
        "by_anchor": sorted(by_anchor, key=lambda x: -x["outstanding"]),
        "by_source": [{"source": k, "name": funding.source_name(k), "amount": rub(v),
                       "on_balance": pricing.FUNDING_SOURCES[k]["on_balance"]} for k, v in by_source.items()],
        "funnel": stages,
        "status_counts": dict(status_counts),
        "gates": gates(s, invs, now, out_amt, overdue30, off, blocked),
        "program_size": prog,
        "anchor_cap": ANCHOR_CAP,
        "industry_cap": INDUSTRY_CAP,
    }


def gates(s: Session, invs: list[Invoice], now: datetime, out_amt: int, overdue30: list[Invoice],
          off: int, blocked: int) -> list[dict]:
    decided = [i for i in invs if i.status not in ("DRAFT", "UPD_VERIFIED", "ACCEPTED", "OFFERED")
               or i.review_flag]
    approved = [i for i in decided if i.funded_at or i.status == "SOLD"]
    approval = D(len(approved)) / len(decided) if decided else D(0)
    hours = [(i.funded_at - i.accepted_at).total_seconds() / 3600 for i in invs if i.funded_at and i.accepted_at]
    hours.sort()
    median = hours[len(hours) // 2] if hours else 0
    p90 = hours[int(len(hours) * 0.9)] if hours else 0
    ov = D(sum(i.amount_kop for i in overdue30)) / out_amt if out_amt else D(0)
    ext = D(off) / out_amt if out_amt else D(0)
    return [
        {"key": "approval", "label": "Доля одобренных счетов", "value": approval, "unit": "share",
         "target": "≥ 85%", "ok": approval >= D("0.85"), "gate": 1},
        {"key": "overdue30", "label": "Просрочка 30+ дней", "value": ov, "unit": "share",
         "target": "≤ 2% портфеля", "ok": ov <= D("0.02"), "gate": 1},
        {"key": "fraud", "label": "Потери от фрода", "value": D(0), "unit": "rub",
         "target": "≈ 0", "ok": True, "gate": 1, "note": f"Заблокировано попыток двойной продажи: {blocked}"},
        {"key": "time_to_money", "label": "Время от акцепта до денег (медиана)", "value": D(str(round(median, 1))),
         "unit": "hours", "target": "< 24 ч", "ok": median < 24, "gate": 1,
         "note": f"90-й процентиль: {round(p90, 1)} ч".replace(".", ",")},
        {"key": "external", "label": "Доля внешнего фондирования", "value": ext, "unit": "share",
         "target": "> 30% (ворота 2)", "ok": ext > D("0.30"), "gate": 2},
    ]


def invoice_dict(s: Session, inv: Invoice, full: bool = False) -> dict:
    link = s.get(SupplierAnchor, (inv.supplier_id, inv.anchor_id))
    in_registry = s.scalar(select(func.count(RegistryEntry.id)).where(RegistryEntry.invoice_id == inv.id)) > 0
    st = ST(inv.status)
    upd_ok = None if st == ST.DRAFT else (inv.plan != "edo_fail")
    acc_ok = None if st in (ST.DRAFT, ST.UPD_VERIFIED) else (st != ST.REJECTED or inv.plan == "edo_fail") and bool(inv.accepted_at)
    d = {
        "id": inv.id, "number": inv.number, "anchor_id": inv.anchor_id, "anchor": inv.anchor.name,
        "anchor_rating": inv.anchor.rating, "supplier_id": inv.supplier_id, "supplier": inv.supplier.name,
        "upd_no": inv.upd_no, "upd_date": inv.upd_date, "amount": rub(inv.amount_kop),
        "term_days": inv.term_days, "due_date": inv.due_date, "status": inv.status,
        "status_label": lifecycle.LABELS[st], "status_reason": inv.status_reason,
        "funding_source": inv.funding_source, "review_flag": inv.review_flag, "review_reason": inv.review_reason,
        "checks": {"upd": upd_ok, "acceptance": acc_ok, "registry": in_registry,
                   "limits": None if not inv.status_reason or "правило" not in (inv.status_reason or "") else False},
        "r_total": inv.r_total, "discount": rub(inv.discount_kop) if inv.discount_kop is not None else None,
        "payout": rub(inv.payout_kop) if inv.payout_kop is not None else None,
        "accepted_at": inv.accepted_at, "funded_at": inv.funded_at, "repaid_at": inv.repaid_at,
        "overdue_since": inv.overdue_since, "story": inv.story, "created_at": inv.t_created,
        "supplier_limit": rub(link.limit_kop) if link else None,
    }
    if full:
        now = get_now(s)
        if st in (ST.ACCEPTED, ST.OFFERED) or inv.r_total is None:
            p = quote(s, inv)
        else:
            p = pricing.price(pricing.PriceInput(face=rub(inv.amount_kop), t_days=inv.term_days,
                                                 r_fund=D(str(inv.r_fund)), pd=pricing.RATING_PD[inv.anchor.rating]))
        d["price"] = p.as_dict()
        d["why"] = explain_price(s, inv)
        d["limit_checks"] = [c.as_dict() for c in limit_checks(s, inv)]
        d["claim_key"] = _claim(inv)
        d["events"] = [
            {"ts": e.ts, "kind": e.kind, "level": e.level, "message": e.message}
            for e in s.scalars(select(Event).where(Event.invoice_id == inv.id, Event.ts <= now)
                               .order_by(Event.ts)).all()
        ]
        d["actions"] = {
            "sell": st == ST.OFFERED and not inv.review_flag,
            "resell": st in (ST.SOLD, ST.FUNDED, ST.OVERDUE, ST.REPAID),
            "overdue": st in (ST.FUNDED, ST.SOLD),
        }
    return d


def anchors_list(s: Session) -> list[Anchor]:
    return s.scalars(select(Anchor).order_by(Anchor.id)).all()


def suppliers_list(s: Session) -> list[Supplier]:
    return s.scalars(select(Supplier).order_by(Supplier.id)).all()
