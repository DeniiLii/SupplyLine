from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from api import sandbox


def get_db(request: Request) -> Iterator[Session]:
    """БД текущего посетителя: копия шаблона в режиме песочницы, общая БД локально."""
    with sandbox.open_session(getattr(request.state, "sid", None)) as s:
        yield s
