"""Shared pytest fixtures.

Placeholders. Each fixture is filled in as its backing module lands; until then
it skips any test that requests it, so the suite stays green and the missing
dependency is named explicitly in the skip message.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def harness() -> Any:
    """Electrical topology under test. Fill in when simulator/harness.py lands."""
    pytest.skip("fixture 'harness' not implemented — awaiting simulator/harness.py")


@pytest.fixture
def epdg() -> Any:
    """EPDG built from `harness`. Fill in when epdg/build.py lands."""
    pytest.skip("fixture 'epdg' not implemented — awaiting epdg/build.py")


@pytest.fixture
def healthy_session() -> Any:
    """Fault-free session. Fill in when simulator/scenarios.py lands."""
    pytest.skip(
        "fixture 'healthy_session' not implemented — awaiting simulator/scenarios.py"
    )


@pytest.fixture
def component_fault_session() -> Any:
    """Session with an injected ComponentFault (drift). Awaiting simulator/faults.py."""
    pytest.skip(
        "fixture 'component_fault_session' not implemented "
        "— awaiting simulator/faults.py"
    )


@pytest.fixture
def sensor_fault_session() -> Any:
    """Session with an injected SensorFault (bias). Awaiting simulator/faults.py."""
    pytest.skip(
        "fixture 'sensor_fault_session' not implemented "
        "— awaiting simulator/faults.py"
    )


@pytest.fixture
def physical_fault_session() -> Any:
    """Session with an injected PhysicalFault (contact resistance).

    The probe-sensitive case — see simulator/intermittent.py.
    """
    pytest.skip(
        "fixture 'physical_fault_session' not implemented "
        "— awaiting simulator/faults.py"
    )
