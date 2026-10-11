"""Запуск без make (Windows): python tasks.py dev|demo|seed|test|build|screens.

Те же цели, что в Makefile. Node берётся из .tools/ (переносной), если его нет в PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def env() -> dict:
    e = os.environ.copy()
    tools = sorted((ROOT / ".tools").glob("node-*"))
    if tools and not shutil.which("node"):
        node_dir = tools[-1] if os.name == "nt" else tools[-1] / "bin"
        e["PATH"] = f"{node_dir}{os.pathsep}{e['PATH']}"
    e.setdefault("PYTHONIOENCODING", "utf-8")
    return e


def py() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def npm(*args: str) -> list[str]:
    exe = shutil.which("npm", path=env()["PATH"]) or "npm"
    return [exe, *args]


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("›", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env(), check=True)


def install() -> None:
    if not VENV_PY.exists():
        run(["uv", "sync"])
    if not (WEB / "node_modules").exists():
        run(npm("install", "--no-audit", "--no-fund"), WEB)


def seed() -> None:
    run([py(), "-m", "db.seed"])


def build() -> None:
    run(npm("run", "build"), WEB)


def test() -> None:
    run([py(), "-m", "pytest", "-q"])
    run(npm("run", "typecheck"), WEB)


def dev() -> None:
    install()
    api = subprocess.Popen([py(), "-m", "uvicorn", "api.main:app", "--port", "8000", "--reload"], cwd=ROOT, env=env())
    try:
        subprocess.run(npm("run", "dev"), cwd=WEB, env=env(), check=False)
    finally:
        api.terminate()


def demo() -> None:
    """Сброс БД, сид, сборка фронтенда, запуск на http://127.0.0.1:8000."""
    install()
    seed()
    build()
    print("\nSupplyLine: http://127.0.0.1:8000\n")
    run([py(), "-m", "uvicorn", "api.main:app", "--port", "8000"])


def screens() -> None:
    run([py(), "scripts/screenshots.py"])


if __name__ == "__main__":
    targets = {f.__name__: f for f in (install, seed, build, test, dev, demo, screens)}
    name = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if name not in targets:
        sys.exit(f"Цели: {', '.join(targets)}")
    targets[name]()
