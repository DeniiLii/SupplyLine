"""Запуск настоящего uvicorn в отдельном процессе для e2e и песочницы (своя временная БД)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def live_server(**env_extra: str):
    port = free_port()
    tmp = Path(tempfile.mkdtemp(prefix="supplyline-live-"))
    env = {**os.environ, "SUPPLYLINE_DB": str(tmp / "db.sqlite3"), "SUPPLYLINE_SESSIONS_DIR": str(tmp / "sessions"),
           "SUPPLYLINE_MOCK_LATENCY": "0", "PYTHONIOENCODING": "utf-8", **env_extra}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while True:
            try:
                with urllib.request.urlopen(base + "/api/ready", timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            if time.time() > deadline or proc.poll() is not None:
                raise RuntimeError("Сервер не поднялся за 90 секунд")
            time.sleep(0.3)
        yield base
    finally:
        proc.terminate()
        proc.wait(10)
