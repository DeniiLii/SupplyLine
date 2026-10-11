import os
import tempfile
from pathlib import Path

# Отдельная БД и без задержек моков: задаётся до импорта приложения
_TMP = Path(tempfile.mkdtemp(prefix="supplyline-test-"))
os.environ.setdefault("SUPPLYLINE_DB", str(_TMP / "test.sqlite3"))
os.environ.setdefault("SUPPLYLINE_MOCK_LATENCY", "0")
