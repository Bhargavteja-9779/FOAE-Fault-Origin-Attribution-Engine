"""Experimental harness topologies — the hypothesis space every generalisation
and Claim 4 result is computed over.

WHY THESE ARE NOT IN A TEST FILE
--------------------------------
handoff.md §5 Rule 1 corollary: any constant that can change an experimental
outcome belongs under audit, never buried in a test module. A topology is the
strongest such constant in this project — it *is* the hypothesis space. Change
a rail's membership and every accuracy figure in validation.md §7 and §8 moves,
with nothing announcing that the experiment is no longer the one that was run.

WHY THEY ARE NOT IN config.py
-----------------------------
`config.SHARED_RAILS` is a statement about the vehicle FOAE is built for.
A, B and C are deliberately fictional harnesses used to test whether footprint
matching TRANSFERS. Filing them next to the production topology would invite
exactly the confusion `epdg/graph.py` already guards against, and `build_epdg`
would have no way to tell which of the five is the real one. They live here,
in one place, imported by both experiments.

CONFIGURATION A IS CROSS-CHECKED AGAINST config
-----------------------------------------------
A is documented as "the current FOAE topology", which makes it a SECOND
hand-written statement of `config.SHARED_RAILS`. Two descriptions of the same
wiring that can drift apart with nothing noticing is the precise failure that
cost this project an investigation (handoff.md §6, SHARED_GROUND_COUPLING), and
the reason `epdg/graph.py::_check_against_harness_segments` exists. So the same
guard is applied here: `_check_topo_a_matches_config()` runs at import and
raises if A stops being an exact relabelling of the production rails.

It compares two descriptions WE wrote. It catches drift between them. It cannot
catch a shared error — if both encode the same wrong belief about the real
vehicle, this passes and the hypothesis space is wrong underneath it. Grounding
the topology against a service-manual wiring diagram is still open (handoff.md
§4 task 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from foae import config


@dataclass(frozen=True)
class Topology:
    name: str
    sensors: tuple[str, ...]
    rails: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def hypotheses(self) -> dict[str, frozenset[str]]:
        """hyp_id -> expected footprint, derived from topology alone."""
        h: dict[str, frozenset[str]] = {}
        for s in self.sensors:
            h[f"CONN:{s}"] = frozenset({s})
        for rid, members in self.rails.items():
            h[f"RAIL:{rid}"] = frozenset(members)
        return h

    def is_rail(self, hyp_id: str) -> bool:
        return hyp_id.startswith("RAIL:")


# Configuration A — the current FOAE topology (config.SHARED_RAILS).
TOPO_A = Topology(
    name="A",
    sensors=("ckp", "map", "ect", "vss", "maf"),
    rails={
        "REF_5V_A": ("ckp", "map"),
        "REF_5V_B": ("vss",),
        "GND_A": ("ckp", "map", "ect"),
        "GND_B": ("vss", "maf"),
    },
)

# Configuration B — structurally different, NOT a relabelling of A:
#   * 7 sensors, not 5
#   * different rail cardinalities (3/2/4/1 vs A's 2/1/3/2)
#   * different overlap pattern: in A, REF_5V_A is a strict subset of GND_A;
#     in B, REF_5V_X and GND_Y are disjoint and GND_X straddles differently
#   * one sensor (egr) sits on no rail at all — a topology feature A lacks
TOPO_B = Topology(
    name="B",
    sensors=("rpm", "tps", "o2", "iat", "baro", "fuelp", "egr"),
    rails={
        "REF_5V_X": ("tps", "o2", "baro"),
        "REF_5V_Y": ("rpm",),
        "GND_X": ("tps", "fuelp"),
        "GND_Y": ("rpm", "iat", "baro", "fuelp"),
    },
)

# Configuration C — structurally different from BOTH A and B.
#   A rail cardinalities: 2/1/3/2   B: 3/1/2/4   C: 4/2/3/3
#   C has NO singleton rail, so it contains no exact connector/rail footprint
#   collision — a structural property neither A nor B has.
TOPO_C = Topology(
    name="C",
    sensors=("cam", "knock", "oilp", "egt", "boost", "lambda"),
    rails={
        "REF_5V_M": ("boost", "lambda", "oilp", "egt"),
        "GND_M": ("cam", "knock"),
        "GND_N": ("oilp", "egt", "boost"),
        "REF_5V_N": ("cam", "knock", "lambda"),
    },
)


# ---------------------------------------------------------------------------
# Drift guard for configuration A
# ---------------------------------------------------------------------------

# A's short names, mapped to the PID names config uses. A is a relabelling of
# the production harness, so this mapping is the whole of the correspondence.
_TOPO_A_ALIASES: dict[str, str] = {
    "ckp": config.PID_ENGINE_RPM,
    "map": config.PID_INTAKE_MAP,
    "ect": config.PID_COOLANT_TEMP,
    "vss": config.PID_VEHICLE_SPEED,
    "maf": config.PID_MAF_RATE,
}

# A's rail ids, mapped to config's. config strips no prefix here; SENSOR_GND_A
# is A's GND_A. Same transform epdg/graph.py::rail_segment_id applies.
_TOPO_A_RAIL_ALIASES: dict[str, str] = {
    "REF_5V_A": config.RAIL_REF_5V_A,
    "REF_5V_B": config.RAIL_REF_5V_B,
    "GND_A": config.RAIL_SENSOR_GND_A,
    "GND_B": config.RAIL_SENSOR_GND_B,
}


def _check_topo_a_matches_config() -> None:
    """Raise if TOPO_A has stopped being a relabelling of config.SHARED_RAILS.

    Deliberately a plain `raise`, not `assert`: assertions vanish under -O, and
    a drift guard that can be optimised away is not a guard.
    """
    declared = {
        _TOPO_A_RAIL_ALIASES[rid]: frozenset(_TOPO_A_ALIASES[s] for s in members)
        for rid, members in TOPO_A.rails.items()
    }
    actual = {
        rid: frozenset(rail["sensors"])  # type: ignore[arg-type]
        for rid, rail in config.SHARED_RAILS.items()
    }

    if set(declared) != set(actual):
        raise ValueError(
            "TOPO_A rails disagree with config.SHARED_RAILS: "
            f"TOPO_A has {sorted(declared)}, config has {sorted(actual)}"
        )
    for rid in sorted(declared):
        if declared[rid] != actual[rid]:
            raise ValueError(
                f"TOPO_A rail {rid} membership drifted from config.SHARED_RAILS: "
                f"TOPO_A says {sorted(declared[rid])}, "
                f"config says {sorted(actual[rid])}"
            )

    mapped = {_TOPO_A_ALIASES[s] for s in TOPO_A.sensors}
    attached = {
        pid for pid in config.PID_NAMES
        if (config.SENSOR_CONNECTOR_MAP.get(pid) or {}).get("connector_id")
    }
    if mapped != attached:
        raise ValueError(
            "TOPO_A sensors disagree with the sensors that have Tier-2 "
            f"connectors in config: TOPO_A has {sorted(mapped)}, "
            f"config has {sorted(attached)}"
        )


_check_topo_a_matches_config()
