"""SQLite-схема. Деньги хранятся в копейках (Integer), чтобы не терять точность."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DB_PATH = Path(os.environ.get("SUPPLYLINE_DB", Path(__file__).with_name("supplyline.sqlite3")))


class Base(DeclarativeBase):
    pass


class Anchor(Base):
    __tablename__ = "anchors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    industry: Mapped[str] = mapped_column(String(80))
    industry_code: Mapped[str] = mapped_column(String(20))
    rating: Mapped[str] = mapped_column(String(1))
    score_points: Mapped[int] = mapped_column(Integer)
    debt_to_ebitda: Mapped[float] = mapped_column(Numeric(6, 2))
    avg_payment_delay_days: Mapped[int] = mapped_column(Integer)
    rejected_acceptance_share: Mapped[float] = mapped_column(Numeric(6, 4))
    business_age_years: Mapped[int] = mapped_column(Integer)
    default_term_days: Mapped[int] = mapped_column(Integer)
    term_min: Mapped[int] = mapped_column(Integer)
    term_max: Mapped[int] = mapped_column(Integer)
    limit_kop: Mapped[int] = mapped_column(Integer)
    supplier_sublimit_kop: Mapped[int] = mapped_column(Integer)
    suppliers: Mapped[list[SupplierAnchor]] = relationship(back_populates="anchor")


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    revenue_mln: Mapped[float] = mapped_column(Numeric(10, 1))
    city: Mapped[str] = mapped_column(String(60))
    auto_sell: Mapped[bool] = mapped_column(default=True)
    links: Mapped[list[SupplierAnchor]] = relationship(back_populates="supplier")


class SupplierAnchor(Base):
    """Связь поставщика с якорем: оборот за 90 дней и стаж работы."""

    __tablename__ = "supplier_anchor"
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), primary_key=True)
    anchor_id: Mapped[int] = mapped_column(ForeignKey("anchors.id"), primary_key=True)
    turnover_90d_kop: Mapped[int] = mapped_column(Integer)
    months_with_anchor: Mapped[int] = mapped_column(Integer)
    returns_share: Mapped[float] = mapped_column(Numeric(6, 4))
    limit_share: Mapped[float] = mapped_column(Numeric(6, 4))
    limit_kop: Mapped[int] = mapped_column(Integer)
    anchor: Mapped[Anchor] = relationship(back_populates="suppliers")
    supplier: Mapped[Supplier] = relationship(back_populates="links")


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(40))
    anchor_id: Mapped[int] = mapped_column(ForeignKey("anchors.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    upd_no: Mapped[str] = mapped_column(String(40))
    upd_date: Mapped[date] = mapped_column(Date)
    amount_kop: Mapped[int] = mapped_column(Integer)
    term_days: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), index=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    funding_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # План событий (сид): когда счёт появляется и движется по автомату без участия пользователя
    t_created: Mapped[datetime] = mapped_column(DateTime, index=True)
    t_upd: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    t_accept: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    t_sold: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    t_funded: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pay_delay_days: Mapped[int] = mapped_column(Integer, default=0)  # 0 — платит в срок
    defaults: Mapped[bool] = mapped_column(default=False)
    plan: Mapped[str] = mapped_column(String(20), default="auto")  # auto | manual | edo_fail | reject
    story: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_flag: Mapped[bool] = mapped_column(default=False)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Факт
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    funded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    overdue_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Цена, зафиксированная в предложении
    r_total: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    r_fund: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    discount_kop: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payout_kop: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spread_kop: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loss_kop: Mapped[int] = mapped_column(Integer, default=0)
    anchor: Mapped[Anchor] = relationship()
    supplier: Mapped[Supplier] = relationship()


class RegistryEntry(Base):
    __tablename__ = "registry"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    holder: Mapped[str] = mapped_column(String(40))


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


def make_engine(path: Path | str | None = None):
    url = f"sqlite:///{path or DB_PATH}"
    eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(eng, "connect")
    def _pragmas(conn, _):  # noqa: ANN001
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(eng=None) -> None:
    Base.metadata.create_all(eng or engine)


def reset_db(eng=None) -> None:
    e = eng or engine
    Base.metadata.drop_all(e)
    Base.metadata.create_all(e)
