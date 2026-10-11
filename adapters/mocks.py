"""Моки внешних систем: задержка 100–800 мс и отказы по настройке.

Никаких реальных подключений: ЭДО, акцепт якоря, платежи и оператор ЦФА имитируются.
Задержку можно отключить переменной окружения SUPPLYLINE_MOCK_LATENCY=0 (тесты).
"""

from __future__ import annotations

import os
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from adapters.ports import AcceptanceDecision, PaymentResult, PortError, UpdCheck


@dataclass
class MockConfig:
    edo_down: bool = False
    anchor_rejects: bool = False
    payment_fails: bool = False
    cfa_down: bool = False
    latency: bool = field(default_factory=lambda: os.environ.get("SUPPLYLINE_MOCK_LATENCY", "1") != "0")


CONFIG = MockConfig()
_rng = random.Random(42)


def _delay() -> None:
    if CONFIG.latency:
        time.sleep(_rng.uniform(0.1, 0.8))


class MockEdo:
    def verify_upd(self, anchor_id: int, supplier_id: int, upd_no: str, upd_date: date,
                   amount: Decimal) -> UpdCheck:
        _delay()
        if CONFIG.edo_down:
            raise PortError("ЭДО", "оператор ЭДО не ответил за 30 секунд")
        return UpdCheck(found=True, upd_no=upd_no, upd_date=upd_date, amount=amount)


class MockAcceptance:
    def request(self, invoice_id: int) -> str:
        _delay()
        return f"acc-{invoice_id}-{uuid.uuid4().hex[:6]}"

    def await_decision(self, request_id: str) -> AcceptanceDecision:
        _delay()
        if CONFIG.anchor_rejects:
            return AcceptanceDecision(False, "Якорь отклонил: расхождение по количеству в УПД")
        return AcceptanceDecision(True)


class MockPayment:
    def payout(self, invoice_id: int, amount: Decimal) -> PaymentResult:
        _delay()
        if CONFIG.payment_fails:
            return PaymentResult(False, "", "Банк-партнёр не подтвердил платёж")
        return PaymentResult(True, f"pay-{invoice_id}-{uuid.uuid4().hex[:8]}")

    def collect(self, invoice_id: int, amount: Decimal) -> PaymentResult:
        _delay()
        if CONFIG.payment_fails:
            return PaymentResult(False, "", "Платёж якоря не поступил")
        return PaymentResult(True, f"col-{invoice_id}-{uuid.uuid4().hex[:8]}")


class MockCfa:
    def issue(self, tranche_id: str, amount: Decimal) -> str:
        _delay()
        if CONFIG.cfa_down:
            raise PortError("Оператор ЦФА", "выпуск недоступен")
        return f"cfa-{tranche_id}"

    def redeem(self, issue_id: str, amount: Decimal) -> PaymentResult:
        _delay()
        return PaymentResult(True, f"red-{issue_id}")


edo = MockEdo()
acceptance = MockAcceptance()
payment = MockPayment()
cfa = MockCfa()
