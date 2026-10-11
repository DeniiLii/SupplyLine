"""Порты внешних систем. В фазе 0 заменяются только реализации (mocks.py → реальные интеграции)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


class PortError(Exception):
    """Внешняя система не ответила или отказала."""

    def __init__(self, system: str, reason: str):
        super().__init__(f"{system}: {reason}")
        self.system, self.reason = system, reason


@dataclass(frozen=True)
class UpdCheck:
    found: bool
    upd_no: str
    upd_date: date
    amount: Decimal
    reason: str = ""


@dataclass(frozen=True)
class AcceptanceDecision:
    accepted: bool
    reason: str = ""


@dataclass(frozen=True)
class PaymentResult:
    ok: bool
    reference: str
    reason: str = ""


class EdoPort(Protocol):
    def verify_upd(self, anchor_id: int, supplier_id: int, upd_no: str, upd_date: date,
                   amount: Decimal) -> UpdCheck: ...


class AcceptancePort(Protocol):
    def request(self, invoice_id: int) -> str: ...

    def await_decision(self, request_id: str) -> AcceptanceDecision: ...


class PaymentPort(Protocol):
    def payout(self, invoice_id: int, amount: Decimal) -> PaymentResult: ...

    def collect(self, invoice_id: int, amount: Decimal) -> PaymentResult: ...


class CfaPort(Protocol):
    def issue(self, tranche_id: str, amount: Decimal) -> str: ...

    def redeem(self, issue_id: str, amount: Decimal) -> PaymentResult: ...
