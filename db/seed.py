"""Детерминированный сид (seed = 42): 5 вымышленных якорей, 40 поставщиков, ~600 счетов за 6 месяцев
и ~120 будущих счетов, которые «появляются» при движении виртуальных часов.

Все названия вымышлены. Реальных компаний, ИНН, логотипов, цен и контрактов нет.
"""

from __future__ import annotations

import math
import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from db.models import Anchor, Invoice, SessionLocal, Setting, Supplier, SupplierAnchor, engine, reset_db
from engine.clock import DEMO_START
from engine.scoring import AnchorMetrics, SupplierMetrics, score_anchor, supplier_limit_share

SEED = 42
HISTORY_DAYS = 180
FUTURE_DAYS = 75

ANCHORS = [
    # name, industry, code, debt/EBITDA, delay, rejected, age, term range, default term, limit ₽ млн, sublimit ₽ млн, weight
    ("Орбита Ритейл", "Непродовольственная розница", "nonfood", "2.6", 5, "0.03", 12, (30, 75), 45, 520, 90, 0.30),
    ("СтройДом", "DIY и товары для дома", "diy", "1.2", 2, "0.01", 15, (30, 90), 60, 480, 90, 0.22),
    ("ТехноМир", "Электроника", "electronics", "2.2", 8, "0.02", 6, (21, 75), 45, 380, 70, 0.18),
    ("МеталлПром", "Промышленность", "industry", "2.8", 14, "0.04", 8, (30, 90), 60, 220, 50, 0.12),
    ("Север-Маркет", "Продовольственная розница", "food", "1.4", 1, "0.015", 18, (8, 40), 25, 450, 70, 0.18),
]

SUPPLIER_STEMS = [
    "Ладога", "Вектор", "Северный ветер", "Кедр", "Гранит", "Меридиан", "Озёрный край", "Тайга",
    "Бирюза", "Полюс", "Сфера", "Каскад", "Ориентир", "Луч", "Янтарь", "Березка", "Атлас", "Магистраль",
    "Пеленг", "Фарватер", "Сапфир", "Рубеж", "Горизонт", "Сокол", "Верста", "Ракета", "Нива", "Звезда",
    "Прибой", "Ковчег", "Аврора", "Фрегат", "Крона", "Регата", "Волна", "Исток", "Купол", "Компас",
    "Дельта", "Пихта",
]
SUPPLIER_SUFFIX = ["Трейд", "Пром", "Продукт", "Снаб", "Логистик", "Мануфактура", "Групп", "Комплект"]
CITIES = ["Тверь", "Казань", "Самара", "Пермь", "Воронеж", "Тула", "Ярославль", "Владимир", "Рязань",
          "Новгород", "Калуга", "Псков"]


def _money(x: float) -> int:
    return int(round(x * 100))


def build(session: Session) -> dict:
    rng = random.Random(SEED)
    now = DEMO_START
    anchors: list[Anchor] = []
    for i, (name, ind, code, de, delay, rej, age, (tmin, tmax), tdef, lim, sub, _w) in enumerate(ANCHORS, 1):
        sc = score_anchor(AnchorMetrics(Decimal(de), delay, Decimal(rej), age))
        a = Anchor(id=i, name=name, industry=ind, industry_code=code, rating=sc.rating,
                   score_points=sc.points, debt_to_ebitda=float(de), avg_payment_delay_days=delay,
                   rejected_acceptance_share=float(rej), business_age_years=age, default_term_days=tdef,
                   term_min=tmin, term_max=tmax, limit_kop=lim * 1_000_000 * 100,
                   supplier_sublimit_kop=sub * 1_000_000 * 100)
        anchors.append(a)
        session.add(a)
    weights = [a[-1] for a in ANCHORS]

    suppliers: list[Supplier] = []
    links: dict[int, list[tuple[int, float]]] = {}
    for j in range(40):
        name = f"ООО «{SUPPLIER_STEMS[j]}-{SUPPLIER_SUFFIX[j % len(SUPPLIER_SUFFIX)]}»"
        revenue = round(rng.uniform(800, 2000), 1)
        s = Supplier(id=j + 1, name=name, revenue_mln=revenue, city=rng.choice(CITIES),
                     auto_sell=rng.random() < 0.8)
        suppliers.append(s)
        session.add(s)
        k = 1 if rng.random() < 0.6 else 2
        chosen = []
        while len(chosen) < k:
            a = rng.choices(range(1, 6), weights=weights)[0]
            if a not in [c for c, _ in chosen]:
                chosen.append((a, 1.0 / (j + 3) ** 0.6))  # неравномерные доли по поставщикам
        links[s.id] = chosen
    session.flush()

    # Активность поставщика: распределение Ципфа, чтобы доли были неравномерными
    pairs: list[tuple[int, int, float]] = []
    for sid, ch in links.items():
        for aid, w in ch:
            pairs.append((sid, aid, w * weights[aid - 1]))

    invoices: list[Invoice] = []
    total_days = HISTORY_DAYS + FUTURE_DAYS
    n_total = 860
    for n in range(n_total):
        day = rng.uniform(0, total_days)
        created = now - timedelta(days=HISTORY_DAYS) + timedelta(days=day)
        created = created.replace(minute=0, second=0, microsecond=0)
        sid, aid, _ = rng.choices(pairs, weights=[p[2] for p in pairs])[0]
        a = anchors[aid - 1]
        amt = math.exp(rng.gauss(math.log(3.2e6), 0.95))
        amt = min(40e6, max(0.5e6, amt))
        amt = round(amt, 2)
        term = int(rng.triangular(a.term_min, a.term_max, a.default_term_days))
        upd_date = created.date()
        t_upd = created + timedelta(hours=rng.uniform(0.5, 6))
        t_accept = t_upd + timedelta(hours=rng.uniform(3, 40))
        # Поставщики без автопродажи подтверждают предложение вручную через 1–4 дня
        auto = suppliers[sid - 1].auto_sell
        t_sold = t_accept + timedelta(hours=rng.uniform(0.3, 3) if auto else rng.uniform(20, 96))
        t_funded = t_sold + timedelta(hours=rng.uniform(1, 19))
        inv = Invoice(
            number=f"SL-{2026}-{n + 1:05d}", anchor_id=aid, supplier_id=sid,
            upd_no=f"{rng.randint(100, 9999)}/{upd_date.month:02d}", upd_date=upd_date,
            amount_kop=_money(amt), term_days=term, due_date=upd_date + timedelta(days=term),
            status="DRAFT", t_created=created, t_upd=t_upd, t_accept=t_accept, t_sold=t_sold,
            t_funded=t_funded, plan="auto",
        )
        invoices.append(inv)
    invoices.sort(key=lambda x: x.t_created)
    for i, inv in enumerate(invoices, 1):
        inv.number = f"SL-{inv.t_created.year}-{i:05d}"

    # Сюжет: ~3% просрочек якорей (чаще у рейтинга C), один дефолт с регрессом
    for inv in invoices:
        r = rng.random()
        base = 0.08 if inv.anchor_id == 4 else 0.018
        if r < base:
            inv.pay_delay_days = rng.choice([5, 9, 14, 21, 38, 45])
    defaulted = next(i for i in invoices if i.anchor_id == 4 and
                     now - timedelta(days=150) < i.t_created < now - timedelta(days=120))
    defaulted.defaults = True
    defaulted.pay_delay_days = 0
    defaulted.story = "default_regress"

    # 1–2 отказа ЭДО и ~1% отказов якоря в акцепте
    past = [i for i in invoices if i.t_created < now - timedelta(days=5)]
    for inv in rng.sample(past, 2):
        inv.plan = "edo_fail"
        inv.story = "edo_fail"
    for inv in rng.sample([i for i in past if i.plan == "auto"], 6):
        inv.plan = "reject"

    # ~2% попыток повторной продажи уже профинансированного требования
    for inv in rng.sample([i for i in past if i.plan == "auto"], 12):
        inv.story = "dup_attempt"

    # «Похожие» счета: та же пара якорь–поставщик, сумма ±0,5%, дата +1…2 дня → на проверку
    for src in rng.sample([i for i in past if i.plan == "auto" and i.story is None], 4):
        twin_created = src.t_created + timedelta(days=rng.choice([1, 2]))
        twin = Invoice(
            number=src.number + "-П", anchor_id=src.anchor_id, supplier_id=src.supplier_id,
            upd_no=f"{rng.randint(100, 9999)}/{src.upd_date.month:02d}",
            upd_date=twin_created.date(),
            amount_kop=int(src.amount_kop * (1 + rng.choice([-0.005, 0.004, 0.003]))),
            term_days=src.term_days, due_date=twin_created.date() + timedelta(days=src.term_days),
            status="DRAFT", t_created=twin_created, t_upd=twin_created + timedelta(hours=2),
            t_accept=twin_created + timedelta(hours=20), t_sold=twin_created + timedelta(hours=21),
            t_funded=twin_created + timedelta(hours=30), plan="auto", story="near_duplicate",
        )
        invoices.append(twin)

    # Свежие предложения для ручной продажи в демо: якорь акцептовал 1–3 дня назад
    fresh = [i for i in invoices if now - timedelta(days=3) < i.t_created < now - timedelta(hours=30)]
    for inv in fresh[:14]:
        inv.plan = "manual"
    # Крупный счёт, который упирается в лимит концентрации (сумма уточняется после прогона часов)
    big = Invoice(
        number="SL-2026-КРУПНЫЙ", anchor_id=1, supplier_id=links_first(links, 1),
        upd_no="7781/10", upd_date=(now - timedelta(days=1)).date(), amount_kop=_money(39_500_000),
        term_days=60, due_date=(now - timedelta(days=1)).date() + timedelta(days=60), status="DRAFT",
        t_created=now - timedelta(days=1, hours=6), t_upd=now - timedelta(days=1, hours=5),
        t_accept=now - timedelta(hours=10), t_sold=now + timedelta(days=999),
        t_funded=now + timedelta(days=999), plan="manual", story="concentration",
    )
    invoices.append(big)
    session.add_all(invoices)

    for sid, ch in links.items():
        for aid, _w in ch:
            a = anchors[aid - 1]
            t90 = sum(i.amount_kop for i in invoices if i.supplier_id == sid and i.anchor_id == aid
                      and now - timedelta(days=90) <= i.t_created <= now)
            t90 = max(t90, _money(rng.uniform(20e6, 60e6)))
            months = rng.choice([3, 8, 14, 26, 40])
            ret = round(rng.uniform(0.0, 0.08), 3)
            share, _rules = supplier_limit_share(SupplierMetrics(
                Decimal(str(suppliers[sid - 1].revenue_mln)), Decimal(t90) / 100, months, Decimal(str(ret))))
            limit = min(int(Decimal(t90) * share), a.supplier_sublimit_kop)
            session.add(SupplierAnchor(supplier_id=sid, anchor_id=aid, turnover_90d_kop=t90,
                                       months_with_anchor=months, returns_share=ret,
                                       limit_share=float(share), limit_kop=limit))
    for k, v in {"now": now.isoformat(), "scenario": "M", "key_rate": "0.14", "seed": str(SEED),
                 "edo_down": "0", "anchor_rejects": "0", "payment_fails": "0", "cfa_down": "0"}.items():
        session.add(Setting(key=k, value=v))
    session.flush()
    return {"anchors": len(anchors), "suppliers": len(suppliers), "invoices": len(invoices)}


def links_first(links: dict[int, list[tuple[int, float]]], anchor_id: int) -> int:
    return next(sid for sid, ch in sorted(links.items()) if any(a == anchor_id for a, _ in ch))


def seed(eng=None) -> dict:
    from api import services  # локальный импорт: services зависит от db

    reset_db(eng or engine)
    with SessionLocal() as s:
        stats = build(s)
        s.commit()
    with SessionLocal() as s:
        services.process_until(s, services.get_now(s), quiet_latency=True)
        services.tune_concentration_story(s)
        s.commit()
        stats["events"] = services.count_events(s)
    return stats


if __name__ == "__main__":
    print(seed())
