"""Electrical Path Dependency Graph — built from design data only.

This is the whole of Claim 2. The graph is derived from the wiring topology in
``config.py`` and nothing else: no training, no fitting, no examples of faults
from the vehicle under test. That is what makes the claim interesting — the
hypothesis space comes from the harness drawing, so it exists for a harness the
system has never seen.

Scope, per docs/enablement_spec.md §1:

  * Tier 2 only. Every OBD-II PID traverses the same CAN pair, so Tier-1 wear is
    common-mode: it moves all sensors together and carries no per-sensor
    attribution signal. Tier 1 enters the system solely through the confound
    gate (``evidence/confound.py``), never through this graph. No PID is mapped
    to a J1962 pin here, and no OBD-II byte offset appears anywhere.

  * ``propagate_wear`` is deliberately NOT implemented. It is deprecated as
    unsound for the reason above: weighting all sensors identically is not
    attribution, and a function that appears to do it invites a claim element
    the bench cannot substantiate.

``control_module_voltage`` gets no node. It is the ECU's own supply
measurement, not a sensor on the harness, so it has no Tier-2 connector — which
is precisely why it works as the Tier-1 confounder detector downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional

from foae import config

# Aliases, so signatures read the way the spec writes them.
SegmentId = str
PidName = str
RailId = str

ECU_NODE_ID: Final[str] = "ECU"
ECU_NODE_LABEL: Final[str] = "ECU"

# Segment id prefixes. These reproduce the hand-written names in
# config.HARNESS_SEGMENTS, which build_epdg cross-checks against.
_SEG_CONNECTOR_PREFIX: Final[str] = "SEG_CONN_"
_SEG_RAIL_PREFIX: Final[str] = "SEG_RAIL_"

# Leading tokens stripped when turning a connector or rail id into a segment id:
# "C_VSS" -> "SEG_CONN_VSS", "SENSOR_GND_A" -> "SEG_RAIL_GND_A". Kept explicit
# rather than inferred so the mapping is auditable.
_CONNECTOR_ID_PREFIX: Final[str] = "C_"
_RAIL_ID_STRIPPED_PREFIX: Final[str] = "SENSOR_"


class NodeKind(str, Enum):
    """The four node kinds in §1. Values are what the JSON export emits."""

    SENSOR = "sensor"
    CONNECTOR = "connector"
    RAIL = "rail"
    ECU = "ecu"


@dataclass(frozen=True)
class EPDGNode:
    id: str
    label: str
    kind: NodeKind


@dataclass(frozen=True)
class EPDGEdge:
    """A directed dependency edge, oriented sensor -> connector -> rail -> ecu.

    ``rail`` is the rail id the edge rides, or None for the sensor's own signal
    leg, which is upstream of any shared rail. A connector that rides both a
    ground and a reference rail produces one edge per rail.
    """

    source: str
    target: str
    rail: Optional[RailId] = None


@dataclass(frozen=True)
class SensorConnection:
    """One sensor's Tier-2 attachment: its connector and the rails it rides."""

    pid: PidName
    connector_id: str
    ground_rail: Optional[RailId] = None
    reference_rail: Optional[RailId] = None

    @property
    def rails(self) -> tuple[RailId, ...]:
        """Rails this sensor rides, deduplicated, in a stable order."""
        seen: list[RailId] = []
        for r in (self.reference_rail, self.ground_rail):
            if r is not None and r not in seen:
                seen.append(r)
        return tuple(seen)


@dataclass(frozen=True)
class HarnessTopology:
    """Design data for one harness. The sole input to the graph.

    Deliberately decoupled from ``config`` so an unseen harness can be described
    and attributed against without touching this module — that portability is
    the Claim 2 argument, and a topology hard-wired to config would not
    demonstrate it.
    """

    name: str
    sensors: tuple[SensorConnection, ...]
    rails: dict[RailId, tuple[PidName, ...]]

    @classmethod
    def from_config(cls, name: str = "FOAE_TIER2") -> HarnessTopology:
        """Build the topology described by config.SENSOR_CONNECTOR_MAP.

        Sensors with no Tier-2 connector (``connector_id is None``) are skipped:
        control_module_voltage is the only such PID and it has no harness
        presence to attribute to.
        """
        sensors: list[SensorConnection] = []
        for pid in config.PID_NAMES:
            spec = config.SENSOR_CONNECTOR_MAP.get(pid)
            if spec is None or spec.get("connector_id") is None:
                continue
            sensors.append(
                SensorConnection(
                    pid=pid,
                    connector_id=str(spec["connector_id"]),
                    ground_rail=spec.get("ground_rail"),  # type: ignore[arg-type]
                    reference_rail=spec.get("reference_rail"),  # type: ignore[arg-type]
                )
            )

        attached = {s.pid for s in sensors}
        rails = {
            rail_id: tuple(
                pid
                for pid in rail["sensors"]  # type: ignore[union-attr]
                if pid in attached
            )
            for rail_id, rail in config.SHARED_RAILS.items()
        }
        return cls(name=name, sensors=tuple(sensors), rails=rails)

    def sensor_for(self, pid: PidName) -> Optional[SensorConnection]:
        for s in self.sensors:
            if s.pid == pid:
                return s
        return None


def connector_segment_id(connector_id: str) -> SegmentId:
    """"C_VSS" -> "SEG_CONN_VSS"."""
    stem = connector_id
    if stem.startswith(_CONNECTOR_ID_PREFIX):
        stem = stem[len(_CONNECTOR_ID_PREFIX):]
    return f"{_SEG_CONNECTOR_PREFIX}{stem}"


def rail_segment_id(rail_id: RailId) -> SegmentId:
    """"REF_5V_A" -> "SEG_RAIL_REF_5V_A"; "SENSOR_GND_A" -> "SEG_RAIL_GND_A"."""
    stem = rail_id
    if stem.startswith(_RAIL_ID_STRIPPED_PREFIX):
        stem = stem[len(_RAIL_ID_STRIPPED_PREFIX):]
    return f"{_SEG_RAIL_PREFIX}{stem}"


@dataclass(frozen=True)
class EPDG:
    """The built graph. Immutable — rebuild rather than mutate."""

    topology: HarnessTopology
    nodes: tuple[EPDGNode, ...]
    edges: tuple[EPDGEdge, ...]
    _footprints: dict[SegmentId, frozenset[PidName]]

    # -- required interface (docs/enablement_spec.md §1) --------------------

    def segments(self) -> list[SegmentId]:
        """Every candidate fault location, in a stable order.

        Tier-2 only: connector segments and shared-rail segments. Tier-1
        (SEG_OBD_*) is intentionally absent — see the module docstring.
        """
        return sorted(self._footprints)

    def sensors_downstream_of(self, segment_id: SegmentId) -> set[PidName]:
        """The footprint of a segment: which PIDs go anomalous if it fails.

        A connector segment implicates exactly its own sensor. A rail segment
        implicates every attached sensor riding that rail.
        """
        if segment_id not in self._footprints:
            raise KeyError(
                f"unknown segment {segment_id!r}; known segments: {self.segments()}"
            )
        return set(self._footprints[segment_id])

    def footprint_matrix(self) -> dict[SegmentId, frozenset[PidName]]:
        """segment id -> footprint, for every segment. The hypothesis space."""
        return {seg: self._footprints[seg] for seg in self.segments()}

    # -- convenience --------------------------------------------------------

    def nodes_of_kind(self, kind: NodeKind) -> tuple[EPDGNode, ...]:
        return tuple(n for n in self.nodes if n.kind is kind)

    def colliding_segments(self) -> list[tuple[SegmentId, ...]]:
        """Groups of segments sharing an identical footprint.

        These are the pairs no passive observation can separate, so attribution
        must abstain on them rather than pick. Surfaced here because the
        collision is a property of the topology, knowable before any data
        arrives. In the current config C_VSS and REF_5V_B collide: the rail
        carries only the one sensor, so a rail fault and a connector fault look
        identical.
        """
        by_footprint: dict[frozenset[PidName], list[SegmentId]] = {}
        for seg in self.segments():
            by_footprint.setdefault(self._footprints[seg], []).append(seg)
        return [tuple(v) for v in by_footprint.values() if len(v) > 1]


def build_epdg(topology: Optional[HarnessTopology] = None) -> EPDG:
    """Build the EPDG from design data. No training, no fitting.

    ``topology`` defaults to the harness described in ``config``. When it does,
    the derived Tier-2 segments are cross-checked against the hand-written
    ``config.HARNESS_SEGMENTS`` and any disagreement raises: two descriptions of
    the same wiring silently drifting apart is the exact failure mode that cost
    this project an investigation (docs/handoff.md §6).
    """
    from_config = topology is None
    if topology is None:
        topology = HarnessTopology.from_config()

    nodes: list[EPDGNode] = []
    edges: list[EPDGEdge] = []
    footprints: dict[SegmentId, frozenset[PidName]] = {}

    # Sensor and connector nodes, and the signal leg between them.
    for sensor in topology.sensors:
        nodes.append(
            EPDGNode(id=sensor.pid, label=sensor.pid, kind=NodeKind.SENSOR)
        )
        nodes.append(
            EPDGNode(
                id=sensor.connector_id,
                label=sensor.connector_id,
                kind=NodeKind.CONNECTOR,
            )
        )
        edges.append(EPDGEdge(source=sensor.pid, target=sensor.connector_id))

        seg = connector_segment_id(sensor.connector_id)
        footprints[seg] = frozenset({sensor.pid})

    # Rail nodes, connector -> rail -> ecu.
    nodes.append(
        EPDGNode(id=ECU_NODE_ID, label=ECU_NODE_LABEL, kind=NodeKind.ECU)
    )
    for rail_id in sorted(topology.rails):
        members = topology.rails[rail_id]
        nodes.append(EPDGNode(id=rail_id, label=rail_id, kind=NodeKind.RAIL))
        footprints[rail_segment_id(rail_id)] = frozenset(members)

        for pid in members:
            sensor = topology.sensor_for(pid)
            if sensor is None:
                raise ValueError(
                    f"rail {rail_id!r} lists sensor {pid!r}, which has no "
                    f"connector in topology {topology.name!r}"
                )
            edges.append(
                EPDGEdge(
                    source=sensor.connector_id, target=rail_id, rail=rail_id
                )
            )
        edges.append(EPDGEdge(source=rail_id, target=ECU_NODE_ID, rail=rail_id))

    # A connector riding no rail at all reaches the ECU directly. None exist in
    # the current config, but an unseen harness may have one (TOPO_B's `egr`
    # in tests/test_generalization.py is exactly this shape).
    for sensor in topology.sensors:
        if not sensor.rails:
            edges.append(
                EPDGEdge(source=sensor.connector_id, target=ECU_NODE_ID)
            )

    epdg = EPDG(
        topology=topology,
        nodes=tuple(_dedupe_nodes(nodes)),
        edges=tuple(dict.fromkeys(edges)),
        _footprints=footprints,
    )

    if from_config:
        _check_against_harness_segments(epdg)
    return epdg


def _dedupe_nodes(nodes: list[EPDGNode]) -> list[EPDGNode]:
    """Preserve first-seen order, drop repeats."""
    seen: dict[str, EPDGNode] = {}
    for n in nodes:
        seen.setdefault(n.id, n)
    return list(seen.values())


def _check_against_harness_segments(epdg: EPDG) -> None:
    """Cross-check derived Tier-2 segments against config.HARNESS_SEGMENTS.

    ``HARNESS_SEGMENTS`` is a second, hand-written statement of the same wiring.
    Two descriptions that can disagree without anything noticing is how
    SHARED_GROUND_COUPLING went unread for an entire investigation, so this
    turns the duplication into an assertion instead of a hazard. Tier-1
    SEG_OBD_* entries are expected to be absent from the graph and are skipped.

    WHAT THIS GUARD DOES NOT DO
    ---------------------------
    It compares two descriptions that WE wrote. It catches drift between them.
    It cannot catch a shared error: if both encode the same wrong belief about
    the real vehicle — the wrong sensors on a rail, a connector that does not
    exist, a rail that is actually two — this check passes and the whole
    hypothesis space is wrong underneath it, silently. A green result here is
    evidence of internal consistency and nothing more.

    Grounding the topology against a service-manual wiring diagram is still
    OPEN. It is task 1 in handoff.md §4 ("Read real harness topology from
    vehicle wiring diagrams"), flagged there as a P0 gap on the ground that our
    current topology is invented and a wrong one degrades Claim 2 with no error
    surfacing anywhere. Claim 2's entire argument is that the graph comes from
    design data, so the graph is only ever as good as that data.
    """
    declared = {
        seg: frozenset(pids)
        for seg, pids in config.HARNESS_SEGMENTS.items()
        if seg.startswith((_SEG_CONNECTOR_PREFIX, _SEG_RAIL_PREFIX))
    }
    derived = epdg.footprint_matrix()

    missing = sorted(set(declared) - set(derived))
    extra = sorted(set(derived) - set(declared))
    if missing or extra:
        raise ValueError(
            "EPDG segments disagree with config.HARNESS_SEGMENTS "
            f"(missing from graph: {missing}; not declared in config: {extra})"
        )

    for seg in sorted(declared):
        if declared[seg] != derived[seg]:
            raise ValueError(
                f"footprint mismatch for {seg}: config.HARNESS_SEGMENTS says "
                f"{sorted(declared[seg])}, graph derives {sorted(derived[seg])}"
            )
