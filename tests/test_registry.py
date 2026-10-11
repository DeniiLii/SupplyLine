import threading
from datetime import date, datetime
from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import Base, RegistryEntry
from engine.registry import ClaimView, claim_key, find_similar, is_similar, normalize_upd_no


def test_key_normalization():
    a = claim_key(1, 2, "№ 0123/10", date(2026, 10, 1), D("1000000.00"))
    b = claim_key(1, 2, "123-10", date(2026, 10, 1), D("1000000"))
    assert a == b and len(a) == 64
    assert claim_key(1, 2, "123/10", date(2026, 10, 1), D("1000000.01")) != a
    assert normalize_upd_no(" 00a-1 ") == "A1"


def test_similar():
    base = ClaimView(1, 1, 2, "1", date(2026, 10, 1), D(1_000_000))
    assert is_similar(base, ClaimView(2, 1, 2, "2", date(2026, 10, 3), D(1_009_000)))
    assert not is_similar(base, ClaimView(2, 1, 2, "2", date(2026, 10, 5), D(1_000_000)))
    assert not is_similar(base, ClaimView(2, 1, 2, "2", date(2026, 10, 2), D(1_020_000)))
    assert not is_similar(base, ClaimView(2, 1, 3, "2", date(2026, 10, 2), D(1_000_000)))
    assert find_similar(base, [base]) == []


def _engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'r.sqlite3'}", connect_args={"check_same_thread": False,
                                                                              "timeout": 30})
    Base.metadata.create_all(eng)
    return eng


def test_unique_index_blocks_duplicate(tmp_path):
    eng = _engine(tmp_path)
    with Session(eng) as s:
        s.add(RegistryEntry(claim_key="k" * 64, invoice_id=1, created_at=datetime(2026, 1, 1), holder="x"))
        s.commit()
        s.add(RegistryEntry(claim_key="k" * 64, invoice_id=2, created_at=datetime(2026, 1, 1), holder="y"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_race_parallel_inserts(tmp_path):
    eng = _engine(tmp_path)
    ok, fail = [], []
    barrier = threading.Barrier(8)

    def worker(n: int) -> None:
        with Session(eng) as s:
            barrier.wait()
            try:
                s.add(RegistryEntry(claim_key="race" + "0" * 60, invoice_id=n, created_at=datetime(2026, 1, 1),
                                    holder=str(n)))
                s.commit()
                ok.append(n)
            except IntegrityError:
                fail.append(n)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with Session(eng) as s:
        rows = s.scalars(select(RegistryEntry)).all()
    assert len(rows) == 1 and len(ok) == 1 and len(fail) == 7
