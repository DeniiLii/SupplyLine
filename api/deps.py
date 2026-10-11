from collections.abc import Iterator

from sqlalchemy.orm import Session

from db.models import SessionLocal


def get_db() -> Iterator[Session]:
    with SessionLocal() as s:
        yield s
