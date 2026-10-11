"""Сценарии фондирования A / B / C / M для операционного демо (не путать с финмоделью)."""

from __future__ import annotations

from decimal import Decimal

from engine.pricing import FUNDING_SOURCES, KEY_RATE, r_fund_blended

D = Decimal

SCENARIOS: dict[str, dict] = {
    "A": {"name": "Банк-партнёр", "weights": {"bank": D(1)}},
    "B": {"name": "Кредитная линия фактору", "weights": {"line": D(1)}},
    "C": {"name": "ЦФА для инвесторов", "weights": {"cfa": D(1)}},
    "M": {"name": "Смешанная структура",
          "weights": {"bank": D("0.60"), "cfa": D("0.25"), "treasury": D("0.10"),
                      "syndication": D("0.05")}},
}


def scenario_rate(code: str, key_rate: Decimal = KEY_RATE) -> Decimal:
    return r_fund_blended(SCENARIOS[code]["weights"], key_rate)


def off_balance_share(code: str) -> Decimal:
    w = SCENARIOS[code]["weights"]
    return sum((v for k, v in w.items() if not FUNDING_SOURCES[k]["on_balance"]), D(0))


def allocate(code: str, seq: int) -> str:
    """Детерминированно назначает источник счёту по порядковому номеру так, чтобы
    доли источников в потоке счетов совпадали с весами сценария (по 20 счетов)."""
    w = SCENARIOS[code]["weights"]
    slot = seq % 20
    acc = D(0)
    for src, share in w.items():
        acc += share * 20
        if slot < acc:
            return src
    return next(iter(w))


def source_name(src: str) -> str:
    return FUNDING_SOURCES[src]["name"]
