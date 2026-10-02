"""Pins Tier-2 attribution and its three abstention paths — spec §2.

Declining is a first-class outcome here, not an error path, so the abstentions
are pinned as tightly as the answers.
"""

from __future__ import annotations

import pytest

from foae import config
from foae.attribution.footprint import (
    GATE_DEGRADED,
    GATE_PASS,
    GATE_TRIPPED,
    REASON_FOOTPRINT_COLLISION,
    REASON_NO_SUPPORTED_HYPOTHESIS,
    REASON_TIER1_CONFOUND,
    Tier1Assessment,
    attribute,
    label_for_segment,
    score_segments,
)
from foae.epdg.graph import EPDG, build_epdg
from foae.evidence.confound import GateAction
from foae.types import FaultLayer

# The S3 observation: Tier-1 transport wear moves every PID at once, including
# control_module_voltage, which has no Tier-2 connector.
S3_OBSERVED = {
    "control_module_voltage",
    "coolant_temp",
    "engine_rpm",
    "intake_map",
    "maf_rate",
    "vehicle_speed",
}

CLEAN = Tier1Assessment(gate=GATE_PASS, confound_score=0.09)


@pytest.fixture(scope="module")
def graph() -> EPDG:
    return build_epdg()


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def test_single_connector_observation_names_that_connector(graph: EPDG) -> None:
    a = attribute({"coolant_temp"}, graph, CLEAN)
    assert a.abstained is False
    assert a.segment_id == "SEG_CONN_ECT"
    assert a.reason is None
    assert a.confidence == pytest.approx(1.0)
    assert a.origin_layer == FaultLayer.PHYSICAL.value


def test_fully_manifested_rail_names_the_rail(graph: EPDG) -> None:
    """S5. Both REF_5V_A sensors clear detection, so the rail footprint matches
    exactly and outscores either connector.
    """
    a = attribute({"engine_rpm", "intake_map"}, graph, CLEAN)
    assert a.abstained is False
    assert a.segment_id == "SEG_RAIL_REF_5V_A"
    assert a.confidence == pytest.approx(1.0)


def test_origin_layer_is_physical_never_interconnect(graph: EPDG) -> None:
    """Spec §4 correction 1: FaultLayer has no 'interconnect' member."""
    a = attribute({"coolant_temp"}, graph, CLEAN)
    assert a.origin_layer == "physical"
    assert a.origin_layer in {m.value for m in FaultLayer}


# ---------------------------------------------------------------------------
# Abstention 1 — tier1_confound
# ---------------------------------------------------------------------------


def test_s3_observation_trips_the_tier1_gate(graph: EPDG) -> None:
    tier1 = Tier1Assessment.from_gate_action(
        GateAction.ABSTAIN, confound_score=0.88, cmv_anomalous=True
    )
    assert tier1.gate == GATE_TRIPPED

    a = attribute(S3_OBSERVED, graph, tier1)
    assert a.abstained is True
    assert a.reason == REASON_TIER1_CONFOUND
    assert a.segment_id is None
    assert a.origin_layer is None
    # No answer, not a weak one.
    assert a.confidence is None
    # The candidates are still returned: they are what justify declining.
    assert len(a.candidates) == 9


def test_cmv_anomalous_alone_trips_the_gate(graph: EPDG) -> None:
    """control_module_voltage has no Tier-2 connector, so its moving means a
    common-mode explanation exists that a Tier-2 verdict would ignore.
    """
    tier1 = Tier1Assessment.from_gate_action(
        GateAction.PROCEED, confound_score=0.05, cmv_anomalous=True
    )
    assert tier1.gate == GATE_TRIPPED


def test_cmv_abstain_is_switchable_and_actually_switches(graph: EPDG) -> None:
    """Spec §2 step 1 requires CMV_ANOMALY_FORCES_ABSTAIN to be sweepable:
    setting it False must change S3's outcome, and if it does not, the CMV path
    is not doing what we think it is. Rule 1 applied to a boolean.
    """
    original = config.CMV_ANOMALY_FORCES_ABSTAIN
    try:
        config.CMV_ANOMALY_FORCES_ABSTAIN = False
        t = Tier1Assessment.from_gate_action(
            GateAction.PROCEED, confound_score=0.05, cmv_anomalous=True
        )
        assert t.gate == GATE_PASS, "flag is off but the gate still tripped"
    finally:
        config.CMV_ANOMALY_FORCES_ABSTAIN = original

    t = Tier1Assessment.from_gate_action(
        GateAction.PROCEED, confound_score=0.05, cmv_anomalous=True
    )
    assert t.gate == GATE_TRIPPED


def test_gate_disabled_on_s3_names_gnd_a_at_exactly_half(graph: EPDG) -> None:
    """THE CLAIM 1 EVIDENCE. Pinned so a future edit cannot erase it silently.

    With the Tier-1 gate disabled, the same S3 observation that the gate
    declines is confidently attributed to a harness segment. This is the only
    Claim 1 figure that does not rest on TIER1_SPURIOUS_ANOMALY_GAIN, which
    currently sits ~14x above its break-even range (validation.md §11).

    The top-2 margin also matters: at 0.1667 it clears TIER2_AMBIGUOUS_MARGIN
    (0.10), so the collision abstention does NOT fire either. Without the gate,
    nothing else in the system stops this answer.
    """
    ungated = attribute(
        S3_OBSERVED, graph, Tier1Assessment(gate=GATE_PASS, confound_score=0.88)
    )
    assert ungated.abstained is False
    assert ungated.segment_id == "SEG_RAIL_GND_A"
    assert ungated.confidence == pytest.approx(0.5)

    margin = ungated.candidates[0].match_score - ungated.candidates[1].match_score
    assert margin == pytest.approx(1 / 6, abs=1e-4)
    assert margin > config.TIER2_AMBIGUOUS_MARGIN


# ---------------------------------------------------------------------------
# Abstention 2 — footprint_collision
# ---------------------------------------------------------------------------


def test_collision_case_abstains(graph: EPDG) -> None:
    """S4. SEG_CONN_VSS and SEG_RAIL_REF_5V_B have identical footprints, so no
    observation can separate them however clean it is.
    """
    a = attribute({"vehicle_speed"}, graph, CLEAN)
    assert a.abstained is True
    assert a.reason == REASON_FOOTPRINT_COLLISION
    assert a.segment_id is None
    # Confidence is RETAINED here, unlike tier1_confound: there is a
    # well-supported explanation, there is just more than one.
    assert a.confidence == pytest.approx(1.0)

    top2 = {c.segment_id for c in a.candidates[:2]}
    assert top2 == {"SEG_CONN_VSS", "SEG_RAIL_REF_5V_B"}


def test_collision_is_a_property_of_the_wiring(graph: EPDG) -> None:
    """Knowable from the topology before any data arrives."""
    assert ("SEG_CONN_VSS", "SEG_RAIL_REF_5V_B") in [
        tuple(sorted(g)) for g in graph.colliding_segments()
    ]


# ---------------------------------------------------------------------------
# Abstention 3 — no_supported_hypothesis
# ---------------------------------------------------------------------------


def test_empty_observation_yields_no_supported_hypothesis(graph: EPDG) -> None:
    """Not reached by S1-S5, but a real outcome of attribute(). Returning either
    other reason here would misstate why we declined.
    """
    a = attribute(set(), graph, CLEAN)
    assert a.abstained is True
    assert a.reason == REASON_NO_SUPPORTED_HYPOTHESIS
    assert a.confidence is None


def test_unexplainable_observation_yields_no_supported_hypothesis(
    graph: EPDG,
) -> None:
    a = attribute({"a_pid_on_no_segment"}, graph, CLEAN)
    assert a.abstained is True
    assert a.reason == REASON_NO_SUPPORTED_HYPOTHESIS


# ---------------------------------------------------------------------------
# Gate vocabulary and scoring
# ---------------------------------------------------------------------------


def test_gate_action_maps_to_contract_vocabulary() -> None:
    m = {
        GateAction.PROCEED: GATE_PASS,
        GateAction.INFLATE: GATE_DEGRADED,
        GateAction.ABSTAIN: GATE_TRIPPED,
    }
    for action, expected in m.items():
        assert Tier1Assessment.from_gate_action(action, 0.2).gate == expected


def test_degraded_still_attributes(graph: EPDG) -> None:
    """DEGRADED means worn but below the abstain threshold: attribution
    proceeds and the verdict reads as lower-trust. It has no downstream consumer
    yet and is in the contract so the state stays visible rather than being
    absorbed into PASS.
    """
    tier1 = Tier1Assessment(gate=GATE_DEGRADED, confound_score=0.4)
    a = attribute({"coolant_temp"}, graph, tier1)
    assert a.abstained is False
    assert a.segment_id == "SEG_CONN_ECT"
    assert tier1.degraded is True


def test_invalid_gate_value_rejected() -> None:
    with pytest.raises(ValueError, match="gate must be one of"):
        Tier1Assessment(gate="MAYBE", confound_score=0.1)


def test_scoring_is_deterministic_and_records_set_arithmetic(graph: EPDG) -> None:
    """Ties break on segment id, so a collision resolves the same way every run
    and the abstention is reproducible.
    """
    a = score_segments({"vehicle_speed"}, graph)
    b = score_segments({"vehicle_speed"}, graph)
    assert [c.segment_id for c in a] == [c.segment_id for c in b]

    rail = next(c for c in a if c.segment_id == "SEG_RAIL_REF_5V_A")
    assert rail.matched == frozenset()
    assert rail.missing == frozenset({"engine_rpm", "intake_map"})
    assert rail.unexpected == frozenset({"vehicle_speed"})


def test_confidence_has_an_honest_alias(graph: EPDG) -> None:
    """It is set agreement, not a calibrated probability."""
    a = attribute({"coolant_temp"}, graph, CLEAN)
    assert a.match_score == a.confidence


def test_labels(graph: EPDG) -> None:
    assert label_for_segment("SEG_RAIL_GND_A") == "GND_A rail"
    assert label_for_segment("SEG_CONN_VSS") == "VSS connector"
