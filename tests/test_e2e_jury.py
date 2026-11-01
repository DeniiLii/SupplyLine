"""Сценарий жюри кликами в браузере (Playwright). По умолчанию не запускается: pytest -m e2e."""

import pytest

from scripts.e2e_demo import run
from tests.server import ROOT, live_server

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(not (ROOT / "web" / "dist" / "index.html").exists(), reason="Нужен собранный web/dist")
@pytest.mark.parametrize("sandbox", ["0", "1"])
def test_jury_scenario(sandbox):
    steps: list[int] = []
    with live_server(SUPPLYLINE_SANDBOX=sandbox) as base:
        run(base, step=lambda n, _text: steps.append(n))
    assert steps == list(range(1, 9))
