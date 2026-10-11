"""Pydantic-схемы входа API с проверкой допустимых значений."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face: Decimal = Field(Decimal(10_000_000), gt=0, le=Decimal(1_000_000_000), description="Номинал счёта, ₽")
    t_days: int = Field(45, ge=1, le=365)
    key_rate: Decimal = Field(Decimal("0.14"), ge=0, le=Decimal("0.5"))
    source: Literal["bank", "line", "cfa", "treasury", "syndication", "mix"] = "bank"
    premium: Decimal | None = Field(None, ge=0, le=Decimal("0.2"), description="Премия к KС; по умолчанию по источнику")
    weights: dict[str, Decimal] | None = Field(None, description="Веса источников для source = mix")
    rating: Literal["A", "B", "C", "D"] = "B"
    pd: Decimal | None = Field(None, ge=0, le=1)
    lgd: Decimal = Field(Decimal("0.6"), ge=0, le=1)
    cover: Decimal = Field(Decimal(0), ge=0, le=Decimal("0.8"))
    r_opex: Decimal = Field(Decimal("0.012"), ge=0, le=Decimal("0.2"))
    r_margin: Decimal = Field(Decimal("0.024"), ge=Decimal("-0.2"), le=Decimal("0.2"))
    mode: Literal[1, 2] = 1
    msp_rate: Decimal = Field(Decimal("0.18"), ge=0, le=Decimal("0.6"))

    @model_validator(mode="after")
    def _weights(self) -> QuoteIn:
        if self.source == "mix":
            w = self.weights or {"bank": Decimal("0.6"), "cfa": Decimal("0.25"), "treasury": Decimal("0.1"),
                                 "syndication": Decimal("0.05")}
            if any(v < 0 for v in w.values()):
                raise ValueError("Веса источников не могут быть отрицательными")
            if abs(sum(w.values()) - 1) > Decimal("0.0001"):
                raise ValueError("Веса источников фондирования должны давать 100%")
            self.weights = w
        return self


class FinRunIn(BaseModel):
    """Переопределения параметров финмодели. Не указанные — из листа «Вводные»."""

    model_config = ConfigDict(extra="forbid")

    scenario: Literal["A", "B", "C", "M"] | None = None
    price_mode: Literal[1, 2] | None = None
    ks_scenario: Literal[1, 2, 3] | None = None
    ks_pass_through: Literal[1, 2] | None = None
    t_days: int | None = Field(None, ge=14, le=90)
    ks_now: Decimal | None = Field(None, ge=0, le=Decimal("0.5"))
    lgd: Decimal | None = Field(None, ge=0, le=1)
    cover: Decimal | None = Field(None, ge=0, le=Decimal("0.8"))
    ins_rate: Decimal | None = Field(None, ge=0, le=Decimal("0.1"))
    r_opex: Decimal | None = Field(None, ge=0, le=Decimal("0.1"))
    r_margin: Decimal | None = Field(None, ge=Decimal("-0.05"), le=Decimal("0.1"))
    msp_rate: Decimal | None = Field(None, ge=0, le=Decimal("0.5"))
    speed_prem: Decimal | None = Field(None, ge=0, le=Decimal("0.1"))
    loss_mult: Decimal | None = Field(None, ge=0, le=10)
    retention: Decimal | None = Field(None, ge=0, le=1)
    cfa_fee: Decimal | None = Field(None, ge=0, le=Decimal("0.01"))
    cap_norm: Decimal | None = Field(None, ge=0, le=1)
    eq_switch: Literal[0, 1] | None = None
    coe: Decimal | None = Field(None, ge=0, le=1)
    tax: Decimal | None = Field(None, ge=0, le=1)
    turnover_bn: list[Decimal] | None = Field(None, min_length=5, max_length=5)
    avg_invoice: Decimal | None = Field(None, gt=0, le=1000)
    var_pct: Decimal | None = Field(None, ge=0, le=Decimal("0.05"))
    fte: list[Decimal] | None = Field(None, min_length=5, max_length=5)
    it: list[Decimal] | None = Field(None, min_length=5, max_length=5)
    comp: list[Decimal] | None = Field(None, min_length=5, max_length=5)
    mkt: list[Decimal] | None = Field(None, min_length=5, max_length=5)
    fte_cost: Decimal | None = Field(None, ge=0, le=10)
    fte_idx: Decimal | None = Field(None, ge=0, le=1)
    ga: Decimal | None = Field(None, ge=0, le=1)
    stress_share: Decimal | None = Field(None, ge=0, le=1)
    stress_month: int | None = Field(None, ge=1, le=60)
    premiums: list[Decimal] | None = Field(None, min_length=5, max_length=5)
    weights_m: list[Decimal] | None = Field(None, min_length=5, max_length=5,
                                            description="Целевые веса сценария M: баланс, линия, ЦФА, казначейства, синдикация")
    months: bool = Field(True, description="Включать помесячный расчёт в ответ")

    @field_validator("turnover_bn", "fte", "it", "comp", "mkt", "premiums")
    @classmethod
    def _non_negative(cls, v: list[Decimal] | None) -> list[Decimal] | None:
        if v is not None and any(x < 0 for x in v):
            raise ValueError("Значения не могут быть отрицательными")
        return v

    @field_validator("weights_m")
    @classmethod
    def _weights(cls, v: list[Decimal] | None) -> list[Decimal] | None:
        if v is None:
            return v
        if any(x < 0 for x in v):
            raise ValueError("Веса не могут быть отрицательными")
        if abs(sum(v) - 1) > Decimal("0.0001"):
            raise ValueError("Веса источников фондирования должны давать 100%")
        return v


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Literal["A", "B", "C", "M"] | None = None
    key_rate: Decimal | None = Field(None, ge=0, le=Decimal("0.5"))
    price_mode: Literal[1, 2] | None = None
    edo_down: bool | None = None
    anchor_rejects: bool | None = None
    payment_fails: bool | None = None
    cfa_down: bool | None = None


class AdvanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(1, ge=0, le=120)
    hours: int = Field(0, ge=0, le=72)
