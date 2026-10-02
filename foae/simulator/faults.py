"""Fault models.

The two faults below are the §5.1 identifiability pair. They are defined by
DIFFERENT PHYSICAL MECHANISMS and are deliberately not parameterised to be
separable — whether they are separable is the empirical question that
tests/test_identifiability.py answers.

Both affect only vehicle_speed, so their passive anomaly footprint is
identical: {vehicle_speed}.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foae import config
from foae.simulator import intermittent

# --- REF_5V_B rail fault parameters ----------------------------------------
# RAIL_QUIESCENT_SAG and RAIL_LOAD_SENSITIVITY now live in config.py
# (handoff.md §5 Rule 1 corollary). Values are unchanged: 0.06 and 0.10.


@dataclass(frozen=True)
class ConnectorDropoutFault:
    """C_VSS — fretted contact in the VSS connector.

    Mechanism: intermittent open circuit. Sample-and-hold through dropouts.
    Probe raises dropout rate, with contact mechanical lag.
    """

    sensor: str = config.PID_VEHICLE_SPEED
    connector_id: str = "C_VSS"
    segment_id: str = "SEG_CONN_VSS"
    severity: float = 1.0

    def apply(
        self,
        true_signal: np.ndarray,
        rate_hz: float,
        rng: np.random.Generator,
        probe: np.ndarray | None = None,
        rail_load: np.ndarray | None = None,
        poll_hz: float = config.SAMPLE_RATE_HZ,
    ) -> np.ndarray:
        """`rail_load` is accepted and IGNORED: a connector-local fault carries
        only its own sensor's current, which is the physical asymmetry under
        test. A probe still couples weakly via common-mode bus activity.

        Returns the measured trace at `poll_hz`."""
        mod = None
        if probe is not None:
            mod = config.CONNECTOR_COMMON_MODE_COUPLING * probe
        gate = intermittent.contact_gate(
            len(true_signal), rate_hz, rng, load_modulation=mod
        )
        if self.severity != 1.0:
            gate = gate & (rng.random(len(gate)) < self.severity)
        return intermittent.apply_dropout_polled(true_signal, gate, rate_hz, poll_hz)


# --- SENSOR_GND_B shared-ground parameters ---------------------------------
# SHARED_GROUND_COUPLING and CONNECTOR_COMMON_MODE_COUPLING now live in
# config.py (handoff.md §5 Rule 1 corollary). SHARED_GROUND_COUPLING is the
# constant that was read by nothing for the whole investigation — see
# handoff.md §6. Values are unchanged: 1.0 and 0.15.


@dataclass(frozen=True)
class SharedGroundIntermittentFault:
    """SENSOR_GND_B — fretted contact on the shared sensor-ground rail,
    early stage.

    Only the VSS leg of the rail has fretted so far, so the manifest footprint
    is {vehicle_speed} — identical to a C_VSS connector fault, and nested
    inside the rail's eventual footprint {vehicle_speed, maf_rate}.

    Mechanism is intermittent dropout, the SAME as ConnectorDropoutFault. The
    faults differ only in what modulates the dropout rate.
    """

    sensor: str = config.PID_VEHICLE_SPEED
    rail_id: str = config.RAIL_SENSOR_GND_B
    segment_id: str = "SEG_RAIL_GND_B"
    severity: float = 1.0

    def apply(
        self,
        true_signal: np.ndarray,
        rate_hz: float,
        rng: np.random.Generator,
        probe: np.ndarray | None = None,
        rail_load: np.ndarray | None = None,
        poll_hz: float = config.SAMPLE_RATE_HZ,
    ) -> np.ndarray:
        """`rail_load` is the co-resident sensor's normalised current draw.

        Returns the measured trace at `poll_hz`."""
        mod = np.zeros(len(true_signal))
        if rail_load is not None:
            mod = mod + config.SHARED_GROUND_COUPLING * rail_load
        if probe is not None:
            # The probe modulates polling of the CO-RESIDENT sensor, so it
            # loads the shared rail directly.
            mod = mod + config.SHARED_GROUND_COUPLING * probe
        gate = intermittent.contact_gate(
            len(true_signal), rate_hz, rng, load_modulation=np.clip(mod, 0.0, 2.0)
        )
        if self.severity != 1.0:
            gate = gate & (rng.random(len(gate)) < self.severity)
        return intermittent.apply_dropout_polled(true_signal, gate, rate_hz, poll_hz)


@dataclass(frozen=True)
class ReferenceRailFault:
    """REF_5V_B — degraded 5V reference rail feeding the VSS.

    Mechanism: resistive divider. Multiplicative scale error that tracks load
    instantaneously (no mechanical inertia).
    """

    rail_id: str = config.RAIL_REF_5V_B
    segment_id: str = "SEG_RAIL_REF_5V_B"
    severity: float = 1.0

    @property
    def affected_sensors(self) -> tuple[str, ...]:
        return tuple(config.SHARED_RAILS[self.rail_id]["sensors"])  # type: ignore[arg-type]

    def apply(
        self,
        true_signal: np.ndarray,
        rate_hz: float,
        rng: np.random.Generator,
        probe: np.ndarray | None = None,
        rail_load: np.ndarray | None = None,
        poll_hz: float = config.SAMPLE_RATE_HZ,
    ) -> np.ndarray:
        """Returns the measured trace at `poll_hz`."""
        sag = np.full(len(true_signal), config.RAIL_QUIESCENT_SAG * self.severity)
        if probe is not None:
            sag = sag + config.RAIL_LOAD_SENSITIVITY * self.severity * probe
        measured = true_signal * (1.0 - sag)
        from foae.simulator import vehicle_model
        return vehicle_model.decimate(measured, rate_hz, poll_hz)
