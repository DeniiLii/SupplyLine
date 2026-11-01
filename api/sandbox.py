"""Песочница на посетителя для публичного демо (SUPPLYLINE_SANDBOX=1).

Шаблонная БД (SUPPLYLINE_DB) сидируется один раз при старте. Каждый посетитель получает cookie sl_sid
и свою копию шаблона в SUPPLYLINE_SESSIONS_DIR: свои часы, счета, настройки и сброс.
Без переменной режим локальный: одна общая БД, как раньше.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from db.models import DB_PATH, SessionLocal, engine, make_engine

ENABLED = os.environ.get("SUPPLYLINE_SANDBOX", "0") == "1"
SESSIONS_DIR = Path(os.environ.get("SUPPLYLINE_SESSIONS_DIR", DB_PATH.parent / "sessions"))
COOKIE = "sl_sid"
TTL_SECONDS = 6 * 3600
MAX_ENGINES = 50
MAX_FILES = 200
RATE_PER_MIN = 120
MAX_BODY = 64 * 1024

_lock = threading.RLock()
_engines: OrderedDict[str, tuple] = OrderedDict()
_ready = threading.Event()
_error: list[str] = []


# ---------------------------------------------------------------- готовность


def is_ready() -> bool:
    return _ready.is_set()


def mark_ready() -> None:
    _ready.set()


def failed() -> str | None:
    return _error[0] if _error else None


def prepare_template() -> None:
    """Сид шаблона в фоне; пока идёт, API отвечает 503, а / — страницей ожидания."""
    try:
        from db.seed import seed

        seed()
        with engine.connect() as c:
            c.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        engine.dispose()
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        _ready.set()
    except Exception as e:  # noqa: BLE001 — показываем причину на /api/ready
        _error.append(f"{type(e).__name__}: {e}")
        raise


# ---------------------------------------------------------------- сессии посетителей


def valid_sid(sid: str | None) -> bool:
    if not sid:
        return False
    try:
        return str(uuid.UUID(sid, version=4)) == sid
    except ValueError:
        return False


def new_sid() -> str:
    return str(uuid.uuid4())


def _path(sid: str) -> Path:
    return SESSIONS_DIR / f"{sid}.sqlite3"


def _remove_files(p: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(p) + suffix).unlink(missing_ok=True)


def _drop_engine(sid: str) -> None:
    item = _engines.pop(sid, None)
    if item:
        item[0].dispose()


def _copy_template(sid: str) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(sid)
    _remove_files(p)
    tmp = p.with_suffix(".tmp")
    shutil.copyfile(DB_PATH, tmp)
    os.replace(tmp, p)


def session_factory(sid: str) -> sessionmaker:
    with _lock:
        if sid in _engines:
            _engines.move_to_end(sid)
            os.utime(_path(sid))
            return _engines[sid][1]
        if not _path(sid).exists():
            _copy_template(sid)
        eng = make_engine(_path(sid))
        factory = sessionmaker(bind=eng, expire_on_commit=False)
        _engines[sid] = (eng, factory)
        while len(_engines) > MAX_ENGINES:
            old, _ = next(iter(_engines.items()))
            _drop_engine(old)
        return factory


def open_session(sid: str | None) -> Session:
    if not ENABLED or sid is None:
        return SessionLocal()
    return session_factory(sid)()


def reset(sid: str) -> dict:
    """Сброс только песочницы этого посетителя: свежая копия шаблона."""
    with _lock:
        _drop_engine(sid)
        _copy_template(sid)
    return {"reset": "session"}


def cleanup(now: float | None = None) -> int:
    """Удаляет копии старше 6 ч и держит не больше MAX_FILES файлов. Возвращает число удалённых."""
    now = now or time.time()
    removed = 0
    with _lock:
        files = sorted(SESSIONS_DIR.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime) \
            if SESSIONS_DIR.exists() else []
        for i, p in enumerate(files):
            if now - p.stat().st_mtime > TTL_SECONDS or len(files) - i > MAX_FILES:
                _drop_engine(p.stem)
                _remove_files(p)
                removed += 1
    return removed


# ---------------------------------------------------------------- ограничение частоты


class RateLimiter:
    """Скользящее окно 60 с в памяти процесса: по cookie посетителя и по IP."""

    def __init__(self, per_min: int) -> None:
        self.per_min = per_min
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = now or time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_min:
                return False
            q.append(now)
            if len(self.hits) > 10_000:
                for k in [k for k, v in self.hits.items() if not v]:
                    del self.hits[k]
            return True


limiter = RateLimiter(RATE_PER_MIN)
ip_limiter = RateLimiter(RATE_PER_MIN * 5)
