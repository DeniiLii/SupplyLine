"""Конечный автомат жизненного цикла счёта. Недопустимый переход — ошибка."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    DRAFT = "DRAFT"
    UPD_VERIFIED = "UPD_VERIFIED"
    ACCEPTED = "ACCEPTED"
    OFFERED = "OFFERED"
    SOLD = "SOLD"
    FUNDED = "FUNDED"
    REPAID = "REPAID"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    OVERDUE = "OVERDUE"
    REGRESS = "REGRESS"
    RECOVERED = "RECOVERED"
    WRITTEN_OFF = "WRITTEN_OFF"


S = Status
TRANSITIONS: dict[Status, set[Status]] = {
    S.DRAFT: {S.UPD_VERIFIED, S.REJECTED},
    S.UPD_VERIFIED: {S.ACCEPTED, S.REJECTED, S.EXPIRED},
    S.ACCEPTED: {S.OFFERED, S.REJECTED, S.EXPIRED},
    S.OFFERED: {S.SOLD, S.EXPIRED, S.REJECTED},
    S.SOLD: {S.FUNDED, S.REJECTED},
    S.FUNDED: {S.REPAID, S.OVERDUE},
    S.OVERDUE: {S.REPAID, S.REGRESS},
    S.REGRESS: {S.RECOVERED, S.WRITTEN_OFF},
    S.REPAID: set(),
    S.REJECTED: set(),
    S.EXPIRED: set(),
    S.RECOVERED: set(),
    S.WRITTEN_OFF: set(),
}
TERMINAL = {s for s, nxt in TRANSITIONS.items() if not nxt}
FINANCED = {S.FUNDED, S.OVERDUE, S.REGRESS}  # деньги выданы и не возвращены

LABELS = {
    S.DRAFT: "Черновик",
    S.UPD_VERIFIED: "УПД проверен",
    S.ACCEPTED: "Акцептован",
    S.OFFERED: "Предложение",
    S.SOLD: "Продан",
    S.FUNDED: "Профинансирован",
    S.REPAID: "Погашен",
    S.REJECTED: "Отклонён",
    S.EXPIRED: "Истёк",
    S.OVERDUE: "Просрочен",
    S.REGRESS: "Регресс",
    S.RECOVERED: "Взыскан",
    S.WRITTEN_OFF: "Списан",
}


class TransitionError(ValueError):
    def __init__(self, src: Status, dst: Status):
        super().__init__(f"Недопустимый переход: {LABELS[src]} → {LABELS[dst]}")
        self.src, self.dst = src, dst


def can(src: Status | str, dst: Status | str) -> bool:
    return Status(dst) in TRANSITIONS[Status(src)]


def transition(src: Status | str, dst: Status | str) -> Status:
    s, d = Status(src), Status(dst)
    if d not in TRANSITIONS[s]:
        raise TransitionError(s, d)
    return d
