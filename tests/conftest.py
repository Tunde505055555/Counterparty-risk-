"""Shared test fixtures.

The suite has two halves:

  * test_schema_shape.py       — offline, structural, always runs (pytest)
  * test_counterparty_risk.py  — behavioural, needs a GenLayer node (gltest)

Run everything with `gltest`, or only the offline half with
`pytest tests/test_schema_shape.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "counterparty_risk.py"
EXAMPLES = ROOT / "examples"

ALLOWED_DOMAINS = json.dumps(["companieshouse.gov.uk", "sec.gov", "trustpilot.com"])
CRITERIA = json.dumps(
    [
        "Operates a real business with verifiable customers",
        "Registered legal entity verifiable in a public registry",
        "Ownership and control are disclosed",
    ]
)
REVIEWER = "0x0000000000000000000000000000000000000001"


@pytest.fixture(scope="session")
def contract_source() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def examples() -> dict:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in EXAMPLES.glob("*.json")
    }


@pytest.fixture
def contract():
    """Deployed CounterpartyRisk. Skips when no GenLayer node is reachable."""
    gltest = pytest.importorskip("gltest", reason="gltest and a GenLayer node are required")
    factory = gltest.get_contract_factory("CounterpartyRisk")
    return factory.deploy(args=[ALLOWED_DOMAINS])
