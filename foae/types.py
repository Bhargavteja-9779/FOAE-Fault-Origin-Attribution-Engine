"""Shared dataclasses and enums — the contracts between modules.

These are the seams described in FOAE_Project_Structure.md section 5. Every
field named there appears here with the same name and meaning. Nothing in this
module imports from any other FOAE module except ``config``, so it can be
imported from anywhere without cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from foae import config

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FaultLayer(str, Enum):
    """The three provenance layers a fault can be attributed to."""

    COMPONENT = "component"
    SENSOR = "sensor"
    PHYSICAL = "physical"


class FaultRegime(str, Enum):
    """How a physical fault manifests electrically.

    The distinction that makes the probe work: ``INTERMITTENT`` responds to
    perturbation, ``FIXED_RESISTANCE`` does not.
    """

    NONE = "none"
    FIXED_RESISTANCE = "fixed_resistance"
    INTERMITTENT = "intermittent"


class ConnectorTier(int, Enum):
    """Which harness tier a fault or evidence item refers to.

    Pin numbers are only meaningful relative to a tier: ``OBD_J1962`` pin 6 is
    CAN-high, while ``SENSOR_HARNESS`` pin 3 is local to whichever sensor
    connector is named alongside it.
    """

    OBD_J1962 = 1      # common-mode transport; affects all PIDs. CW-AI's domain.
    SENSOR_HARNESS = 2  # per-sensor signal path; what the EPDG operates on.


class RailKind(str, Enum):
    """Type of shared Tier-2 rail. Values match config.RAIL_KIND_*."""

    REFERENCE = "reference"
    GROUND = "ground"


class WearClass(str, Enum):
    """CW-AI connector-wear severity bands."""

    PRISTINE = "pristine"
    LIGHT = "light"
    MODERATE = "moderate"
    SEVERE = "severe"


class VehicleState(str, Enum):
    """Operating state used by the probe safety envelope.

    Members whose values appear in ``config.EXCLUDED_VEHICLE_STATES`` are
    states in which a probe must be denied.
    """

    KEY_ON_ENGINE_OFF = "key_on_engine_off"
    CRANKING = "cranking"
    IDLE = "idle"
    STEADY_CRUISE = "steady_cruise"
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"
    WIDE_OPEN_THROTTLE = "wide_open_throttle"
    LIMP_HOME = "limp_home"
    AIRBAG_DEPLOYED = "airbag_deployed"
    DTC_ACTIVE_SAFETY_CRITICAL = "dtc_active_safety_critical"

    @property
    def probe_excluded(self) -> bool:
        return self.value in config.EXCLUDED_VEHICLE_STATES


class Polarity(int, Enum):
    """Sign of a stimulus-response relationship."""

    NEGATIVE = -1
    NONE = 0
    POSITIVE = 1


class SafetyVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class DenyReason(str, Enum):
    """Why a probe was refused. Recorded in the audit log."""

    EXCLUDED_STATE = "excluded_state"
    COOLDOWN_ACTIVE = "cooldown_active"
    BUS_UTILISATION = "bus_utilisation"
    DURATION_EXCEEDED = "duration_exceeded"
    WATCHDOG_TIMEOUT = "watchdog_timeout"


class GateDecision(str, Enum):
    """Layer-4 technical effect: what the controller does to the DTC."""

    CONFIRM = "confirm"
    SUPPRESS = "suppress"
    RETAG = "retag"


class EmbodimentKind(str, Enum):
    INTEGRATED = "integrated"
    SERVICE_TOOL = "service_tool"


# ---------------------------------------------------------------------------
# Layer 1 — data source
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FaultLabel:
    """Ground truth attached to a simulated session."""

    layer: Optional[FaultLayer]
    regime: FaultRegime = FaultRegime.NONE
    affected_sensors: tuple[str, ...] = ()
    # Pin numbers are interpreted relative to `tier`. For SENSOR_HARNESS faults
    # they are local to `connector_id`; for OBD_J1962 they are J1962 pins.
    tier: Optional[ConnectorTier] = None
    affected_pins: tuple[int, ...] = ()
    connector_id: Optional[str] = None
    rail_id: Optional[str] = None
    magnitude: float = 0.0
    onset_s: float = 0.0
    segment_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.affected_pins and self.tier is None:
            raise ValueError("affected_pins given without a tier to interpret them")
        if self.tier is ConnectorTier.SENSOR_HARNESS and self.affected_pins:
            if self.connector_id is None and self.rail_id is None:
                raise ValueError(
                    "Tier-2 pin fault needs a connector_id or rail_id to scope it"
                )

    @property
    def is_healthy(self) -> bool:
        return self.layer is None


@dataclass
class Session:
    """One diagnostic session: timestamps plus the six PID traces."""

    session_id: str
    data: pd.DataFrame
    vehicle_state: VehicleState = VehicleState.STEADY_CRUISE
    label: Optional[FaultLabel] = None
    sample_rate_hz: float = config.SAMPLE_RATE_HZ
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return len(self.data) / self.sample_rate_hz


# ---------------------------------------------------------------------------
# Layer 2 — evidence
# ---------------------------------------------------------------------------


@dataclass
class CWAIOutput:
    """Output of the filed CW-AI patent, treated here as a black box.

    Tier 1 only: the 16-element vector and the resistance map are both indexed
    by J1962 pin. Because all PIDs share that connector, this evidence is
    common-mode — it constrains whether the OBD-II link is healthy but does not
    by itself discriminate between sensors. Per-sensor attribution comes from
    Tier-2 evidence in the EPDG.
    """

    per_pin_error_vector: np.ndarray  # shape (config.NUM_PINS,) == (16,)
    contact_resistance_ohm: dict[int, float]  # J1962 pin -> ohms
    wear_class: WearClass
    uncertainty: float
    tier: ConnectorTier = ConnectorTier.OBD_J1962

    def __post_init__(self) -> None:
        if self.per_pin_error_vector.shape != (config.NUM_PINS,):
            raise ValueError(
                f"per_pin_error_vector must have shape ({config.NUM_PINS},), "
                f"got {self.per_pin_error_vector.shape}"
            )


@dataclass
class ConnectorWearEvidence:
    """Tier-2 wear evidence for one sensor-harness connector or shared rail.

    The EPDG's working unit. Exactly one of `connector_id` / `rail_id` is set:
    a connector fault implicates a single sensor, a rail fault implicates every
    sensor on that rail (see config.SHARED_RAILS).
    """

    evidence: float
    affected_sensors: tuple[str, ...]
    connector_id: Optional[str] = None
    rail_id: Optional[str] = None
    contact_resistance_ohm: Optional[float] = None
    tier: ConnectorTier = ConnectorTier.SENSOR_HARNESS

    def __post_init__(self) -> None:
        if (self.connector_id is None) == (self.rail_id is None):
            raise ValueError("set exactly one of connector_id or rail_id")


@dataclass
class PlausibilityResult:
    """Residuals against the known PID physics relationships."""

    relationship_residuals: dict[str, float]
    anomalous_relationships: list[str]
    overall_score: float = 0.0


class ResponseChannel(str, Enum):
    """Which response channel a signature is expressed in."""

    SIGNED = "signed"       # additive coupling: stimulus shifts the value
    ENVELOPE = "envelope"   # modulating coupling: stimulus changes disturbance energy


@dataclass
class ProbeSignature:
    """Expected perturbation response for one harness segment.

    ``signatures.match()`` compares a measured ProbeResult against the library
    of these to identify which segment produced the response.

    REDUCED 2026-08-05 on empirical grounds. This dataclass previously carried
    `expected_lag_ms` and `expected_polarity`. Across both identifiability
    experiments (tests/test_identifiability*.py, 50 seeds each) neither field
    discriminated:

        signed_lag_ms      AUC 0.618 / 0.542 / 0.532
        envelope_lag_ms    AUC 0.677 / 0.552
        polarity stability 0.54-0.62 for BOTH classes (chance is 0.50)

    Magnitude carried all the discrimination that existed. Keeping unsupported
    fields in a patent-facing structure invites a claim element the bench rig
    cannot substantiate, so they are removed rather than left aspirational.

    If bench measurement later shows lag or polarity to be informative on real
    fretted contacts, reinstate them WITH the measurement that justifies it.
    """

    segment_id: str
    expected_magnitude_range: tuple[float, float]
    response_channel: ResponseChannel
    affected_sensors: tuple[str, ...]

    def __post_init__(self) -> None:
        low, high = self.expected_magnitude_range
        if low > high:
            raise ValueError(
                f"expected_magnitude_range must be (low, high), got {low} > {high}"
            )


@dataclass
class ProbeResult:
    """Measured response to one perturbation."""

    response_correlations: dict[str, float]
    response_lags: dict[str, float]        # sensor -> lag in ms
    response_polarities: dict[str, Polarity]
    responding_sensors: list[str]
    matched_segment_id: Optional[str] = None
    match_score: float = 0.0
    perturbation_id: str = ""


@dataclass(frozen=True)
class SafetyDecision:
    """Verdict from the safety envelope, written to the audit log."""

    verdict: SafetyVerdict
    reason: Optional[DenyReason] = None
    vehicle_state: Optional[VehicleState] = None
    detail: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict is SafetyVerdict.ALLOW


@dataclass
class ProbeAuditRecord:
    """One immutable line of the probe audit trail."""

    timestamp: float
    session_id: str
    perturbation_id: str
    safety_decision: SafetyDecision
    triggering_uncertainty: float
    duration_s: float = 0.0
    bus_util_delta: float = 0.0


# ---------------------------------------------------------------------------
# Layer 3 — inference
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceVector:
    """Attribution across the three layers, with uncertainty.

    ``component``, ``sensor``, and ``physical`` are the per-layer scores; they
    are expected to sum to approximately 1.0.
    """

    component: float
    sensor: float
    physical: float
    epistemic_uncertainty: float
    confidence: float
    calibrated: bool = False
    coverage_level: Optional[float] = None

    @property
    def argmax_layer(self) -> FaultLayer:
        scores = {
            FaultLayer.COMPONENT: self.component,
            FaultLayer.SENSOR: self.sensor,
            FaultLayer.PHYSICAL: self.physical,
        }
        return max(scores, key=lambda layer: scores[layer])

    @property
    def needs_probe(self) -> bool:
        return self.epistemic_uncertainty > config.UNCERTAINTY_PROBE_THRESHOLD


@dataclass
class FeatureVector:
    """Assembled model input. ``names`` labels ``values`` elementwise."""

    values: np.ndarray
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.values.shape != (len(self.names),):
            raise ValueError(
                f"values shape {self.values.shape} does not match "
                f"{len(self.names)} feature names"
            )


# ---------------------------------------------------------------------------
# Layer 4 — control
# ---------------------------------------------------------------------------


@dataclass
class GateOutput:
    """The technical effect: what happens to the DTC."""

    decision: GateDecision
    dtc_code: str
    attributed_origin: FaultLayer
    provenance_vector: ProvenanceVector
    probe_fired: bool
    sessions_confirmed: int = 0
    rationale: str = ""


@dataclass
class PipelineResult:
    """Everything one end-to-end session produced. Consumed by validation and
    the dashboard."""

    session_id: str
    gate_output: GateOutput
    cwai_output: Optional[CWAIOutput] = None
    plausibility: Optional[PlausibilityResult] = None
    sensor_wear_evidence: dict[str, float] = field(default_factory=dict)
    probe_result: Optional[ProbeResult] = None
    audit_records: list[ProbeAuditRecord] = field(default_factory=list)
    ground_truth: Optional[FaultLabel] = None
