"""Pins the EPDG's structure — docs/enablement_spec.md §1.

The graph is the whole of Claim 2: the hypothesis space comes from the wiring
drawing, so it exists for a harness the system has never seen. These tests fix
the structure that claim rests on, so a topology or id-scheme edit cannot change
it silently.
"""

from __future__ import annotations

import pytest

from foae import config
from foae.epdg.graph import (
    ECU_NODE_ID,
    EPDG,
    HarnessTopology,
    NodeKind,
    build_epdg,
    connector_segment_id,
    rail_segment_id,
)

# The nine Tier-2 segments the current topology yields: one per sensor
# connector, one per shared rail. Written out rather than derived, so a change
# to config has to come here and be argued for.
EXPECTED_SEGMENTS = [
    "SEG_CONN_CKP",
    "SEG_CONN_ECT",
    "SEG_CONN_MAF",
    "SEG_CONN_MAP",
    "SEG_CONN_VSS",
    "SEG_RAIL_GND_A",
    "SEG_RAIL_GND_B",
    "SEG_RAIL_REF_5V_A",
    "SEG_RAIL_REF_5V_B",
]

EXPECTED_FOOTPRINTS = {
    "SEG_CONN_CKP": {"engine_rpm"},
    "SEG_CONN_ECT": {"coolant_temp"},
    "SEG_CONN_MAF": {"maf_rate"},
    "SEG_CONN_MAP": {"intake_map"},
    "SEG_CONN_VSS": {"vehicle_speed"},
    "SEG_RAIL_REF_5V_A": {"engine_rpm", "intake_map"},
    "SEG_RAIL_REF_5V_B": {"vehicle_speed"},
    "SEG_RAIL_GND_A": {"coolant_temp", "engine_rpm", "intake_map"},
    "SEG_RAIL_GND_B": {"maf_rate", "vehicle_speed"},
}


@pytest.fixture(scope="module")
def graph() -> EPDG:
    return build_epdg()


def test_build_epdg_yields_the_nine_expected_segments(graph: EPDG) -> None:
    assert graph.segments() == EXPECTED_SEGMENTS


def test_footprints_match_the_wiring(graph: EPDG) -> None:
    matrix = {seg: set(pids) for seg, pids in graph.footprint_matrix().items()}
    assert matrix == EXPECTED_FOOTPRINTS


def test_sensors_downstream_of_agrees_with_the_matrix(graph: EPDG) -> None:
    for seg, expected in EXPECTED_FOOTPRINTS.items():
        assert graph.sensors_downstream_of(seg) == expected


def test_unknown_segment_raises(graph: EPDG) -> None:
    with pytest.raises(KeyError):
        graph.sensors_downstream_of("SEG_RAIL_DOES_NOT_EXIST")


def test_control_module_voltage_has_no_node(graph: EPDG) -> None:
    """It is the ECU's own supply measurement, not a sensor on the harness.

    Having no Tier-2 connector is exactly why it works as the Tier-1 confounder
    detector downstream — if it ever gained a node, the confound gate's premise
    would be gone and nothing else would notice.
    """
    ids = {n.id for n in graph.nodes}
    assert config.PID_CONTROL_MODULE_VOLTAGE not in ids

    every_footprint = set().union(*graph.footprint_matrix().values())
    assert config.PID_CONTROL_MODULE_VOLTAGE not in every_footprint


def test_no_tier1_segments_in_the_graph(graph: EPDG) -> None:
    """Tier 1 is common-mode and enters only through the confound gate."""
    assert not [s for s in graph.segments() if s.startswith("SEG_OBD_")]


def test_colliding_segments_is_exactly_the_vss_ref5vb_pair(graph: EPDG) -> None:
    """REF_5V_B carries only vehicle_speed, so a fault on that rail and one in
    the VSS connector predict the same sensor and cannot be told apart.

    This is the honest limit of Claim 2 and the S4 scenario. It is a property of
    the wiring, knowable before any data arrives.
    """
    collisions = [tuple(sorted(g)) for g in graph.colliding_segments()]
    assert collisions == [("SEG_CONN_VSS", "SEG_RAIL_REF_5V_B")]


def test_node_kinds_and_ecu_sink(graph: EPDG) -> None:
    kinds = {k: len(graph.nodes_of_kind(k)) for k in NodeKind}
    assert kinds[NodeKind.SENSOR] == 5      # cmv excluded
    assert kinds[NodeKind.CONNECTOR] == 5
    assert kinds[NodeKind.RAIL] == 4
    assert kinds[NodeKind.ECU] == 1

    # Every rail terminates at the single ECU sink.
    rail_ids = {n.id for n in graph.nodes_of_kind(NodeKind.RAIL)}
    to_ecu = {e.source for e in graph.edges if e.target == ECU_NODE_ID}
    assert rail_ids <= to_ecu


def test_signal_leg_carries_no_rail_and_rail_edges_do(graph: EPDG) -> None:
    """Spec §4 correction 2: the sensor's own leg is upstream of any shared
    rail, so it carries rail=None. A connector on both a ground and a reference
    rail emits one edge per rail, so no single edge can name "the" rail.
    """
    sensors = {n.id for n in graph.nodes_of_kind(NodeKind.SENSOR)}
    for e in graph.edges:
        if e.source in sensors:
            assert e.rail is None
        else:
            assert e.rail is not None

    ckp_rails = {e.rail for e in graph.edges if e.source == "C_CKP"}
    assert ckp_rails == {config.RAIL_REF_5V_A, config.RAIL_SENSOR_GND_A}


def test_propagate_wear_is_not_implemented() -> None:
    """Deprecated as unsound: Tier-1 wear is common-mode and weights all
    sensors identically, so a function that appears to do it invites a claim
    element the bench cannot substantiate (spec §1).
    """
    assert not hasattr(build_epdg(), "propagate_wear")


def test_id_transforms_round_trip() -> None:
    assert connector_segment_id("C_VSS") == "SEG_CONN_VSS"
    assert rail_segment_id("SENSOR_GND_A") == "SEG_RAIL_GND_A"
    assert rail_segment_id("REF_5V_A") == "SEG_RAIL_REF_5V_A"


def test_graph_is_portable_to_an_unseen_harness() -> None:
    """Claim 2's actual argument: no training, no fitting, no examples from the
    target vehicle. A topology never seen before must produce a usable
    hypothesis space from design data alone.
    """
    from foae.epdg.graph import SensorConnection

    topo = HarnessTopology(
        name="UNSEEN",
        sensors=(
            SensorConnection("alpha", "C_ALPHA", ground_rail="GND_Z"),
            SensorConnection("beta", "C_BETA", ground_rail="GND_Z"),
        ),
        rails={"GND_Z": ("alpha", "beta")},
    )
    g = build_epdg(topo)
    assert g.segments() == ["SEG_CONN_ALPHA", "SEG_CONN_BETA", "SEG_RAIL_GND_Z"]
    assert g.sensors_downstream_of("SEG_RAIL_GND_Z") == {"alpha", "beta"}


def test_config_cross_check_rejects_a_drifted_topology() -> None:
    """build_epdg cross-checks derived segments against config.HARNESS_SEGMENTS
    when it builds from config. Two descriptions of one harness that can drift
    apart is the hazard in handoff.md §6, so confirm the guard actually bites.
    """
    original = config.HARNESS_SEGMENTS
    try:
        config.HARNESS_SEGMENTS = {
            k: v for k, v in original.items() if k != "SEG_RAIL_GND_B"
        }
        with pytest.raises(ValueError, match="disagree with config.HARNESS_SEGMENTS"):
            build_epdg()
    finally:
        config.HARNESS_SEGMENTS = original
    build_epdg()  # restored
