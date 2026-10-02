"""Tier-2 footprint attribution over the EPDG — docs/enablement_spec.md §2.

Given the set of PIDs observed anomalous, rank the candidate harness segments by
how well each one's footprint explains that set, and either name a segment or
decline to answer.

Declining is a first-class outcome here, not an error path. Two things make a
Tier-2 verdict unsafe, and each has its own abstention:

  * ``tier1_confound`` — a common-mode explanation exists that a Tier-2 verdict
    would ignore. Something is moving every PID at once, so any per-segment
    story is suspect. Worn diagnostic transport is one such cause; an anomalous
    ``control_module_voltage`` is another signal of it, since that PID has no
    Tier-2 connector. Note it can also move from charging-system or battery
    causes, so this reason deliberately does NOT assert that Tier 1 is
    degraded — only that a common-mode explanation is live and unexamined.

  * ``footprint_collision`` — two segments predict the same set of sensors, so
    the observation cannot distinguish them however clean it is. This is a
    property of the wiring, knowable from the topology before any data arrives
    (``EPDG.colliding_segments``). In the current harness REF_5V_B carries only
    vehicle_speed, so a fault on that rail and a fault in the VSS connector are
    indistinguishable.

A system that declines when it cannot answer is a stronger claim than one that
is always confident, and the second case above is the honest limit of Claim 2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from foae import config
from foae.epdg.graph import EPDG, NodeKind, PidName, SegmentId
from foae.evidence.confound import GateAction
from foae.types import FaultLayer

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
#
# These string values are the JSON export contract (spec §4) and the dashboard
# switches on them directly. Do not rename them.
#
# The gate is three-state, mirroring evidence/confound.py's GateAction:
#   PROCEED -> PASS, INFLATE -> DEGRADED, ABSTAIN -> TRIPPED.
# DEGRADED means Tier 1 is worn but below the abstain threshold. Attribution
# proceeds and the verdict should be read as lower-trust. It has no downstream
# consumer yet; it is carried in the contract so the state stays VISIBLE rather
# than being absorbed into PASS and quietly lost.

GATE_PASS = "PASS"
GATE_DEGRADED = "DEGRADED"
GATE_TRIPPED = "TRIPPED"

GATE_STATES = (GATE_PASS, GATE_DEGRADED, GATE_TRIPPED)

REASON_TIER1_CONFOUND = "tier1_confound"
REASON_FOOTPRINT_COLLISION = "footprint_collision"

# Reached when no hypothesis clears config.FOOTPRINT_MATCH_FLOOR — an empty
# anomaly set, or one explainable by no segment in the graph. Returning either
# of the other two reasons here would misstate why we declined, so it gets its
# own value and is documented in the contract alongside them.
REASON_NO_SUPPORTED_HYPOTHESIS = "no_supported_hypothesis"

# PROTOTYPE reason, reachable only when config.ABSTAIN_ON_NESTED_FOOTPRINT is
# enabled. Default is off, so this does not appear in any shipped export.
REASON_NESTED_FOOTPRINT = "nested_footprint"

REASONS = (
    REASON_TIER1_CONFOUND,
    REASON_FOOTPRINT_COLLISION,
    REASON_NO_SUPPORTED_HYPOTHESIS,
    REASON_NESTED_FOOTPRINT,
)

# Every Tier-2 segment is wiring, so attribution lands on the physical layer.
# FaultLayer has no "interconnect" member; see the correction note in spec §4.
ORIGIN_LAYER_TIER2 = FaultLayer.PHYSICAL.value


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tier1Assessment:
    """Tier-1 confounder state for one session, in export vocabulary."""

    gate: str
    confound_score: float
    threshold: float = config.TIER1_CONFOUND_THRESHOLD
    cmv_anomalous: bool = False

    def __post_init__(self) -> None:
        if self.gate not in GATE_STATES:
            raise ValueError(
                f"gate must be one of {GATE_STATES}, got {self.gate!r}"
            )

    @property
    def tripped(self) -> bool:
        return self.gate == GATE_TRIPPED

    @property
    def degraded(self) -> bool:
        """Derived view of ``gate``, not a second stored fact."""
        return self.gate == GATE_DEGRADED

    @classmethod
    def from_gate_action(
        cls,
        action: GateAction,
        confound_score: float,
        cmv_anomalous: bool = False,
    ) -> Tier1Assessment:
        """Translate evidence/confound.py's GateAction into the contract.

        PROCEED -> PASS, INFLATE -> DEGRADED, ABSTAIN -> TRIPPED.

        An anomalous ``control_module_voltage`` also trips, when
        ``config.CMV_ANOMALY_FORCES_ABSTAIN`` is set. Be precise about why:
        control_module_voltage has no Tier-2 connector, but it can move from
        charging-system or battery causes — a failing alternator, a weak
        battery — not only from connector wear. So the justification is NOT
        "Tier 1 is degraded", which would assert a cause we have not
        established. It is that A COMMON-MODE EXPLANATION EXISTS THAT A TIER-2
        VERDICT WOULD IGNORE: something is moving every PID at once, we do not
        know what, and naming a harness segment would silently discard that
        possibility. Same abstention, accurate reason.
        """
        if action is GateAction.ABSTAIN:
            gate = GATE_TRIPPED
        elif action is GateAction.INFLATE:
            gate = GATE_DEGRADED
        else:
            gate = GATE_PASS

        if cmv_anomalous and config.CMV_ANOMALY_FORCES_ABSTAIN:
            gate = GATE_TRIPPED

        return cls(
            gate=gate,
            confound_score=confound_score,
            cmv_anomalous=cmv_anomalous,
        )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """One scored hypothesis.

    ``match_score`` is set agreement (Jaccard) between the segment's predicted
    footprint and what was actually observed. The raw set arithmetic is kept
    alongside it because the score alone hides which direction a hypothesis
    failed in: ``missing`` means the segment predicts sensors that stayed quiet,
    ``unexpected`` means sensors moved that this segment cannot explain.
    """

    segment_id: SegmentId
    label: str
    match_score: float
    footprint: frozenset[PidName]
    matched: frozenset[PidName]
    missing: frozenset[PidName]
    unexpected: frozenset[PidName]


@dataclass(frozen=True)
class Attribution:
    """The verdict. Field names are the spec §4 export contract.

    ``confidence`` IS ``match_score`` — a set-agreement score in [0, 1]. It is
    NOT a calibrated probability and must never be reported as one: nothing here
    is fitted to outcome frequencies, so 0.86 does not mean 86% of such calls
    are right. The ``match_score`` alias below exists so downstream code can use
    the honest name; the conformal layer that would make a calibrated number is
    explicitly out of scope (spec §5).
    """

    origin_layer: Optional[str]
    segment_id: Optional[SegmentId]
    confidence: Optional[float]
    abstained: bool
    reason: Optional[str]
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)

    @property
    def match_score(self) -> Optional[float]:
        """Honest alias for ``confidence``. Uncalibrated set agreement."""
        return self.confidence

    @property
    def top(self) -> Optional[Candidate]:
        return self.candidates[0] if self.candidates else None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def label_for_segment(segment_id: SegmentId) -> str:
    """Human label for the dashboard: SEG_RAIL_GND_A -> 'GND_A rail'."""
    if segment_id.startswith("SEG_CONN_"):
        return f"{segment_id[len('SEG_CONN_'):]} connector"
    if segment_id.startswith("SEG_RAIL_"):
        return f"{segment_id[len('SEG_RAIL_'):]} rail"
    return segment_id


def _jaccard(a: frozenset[PidName], b: frozenset[PidName]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def soft_membership(ratio: float) -> float:
    """Residual ratio -> probability the sensor is genuinely elevated.

    Logistic centred on ``config.ANOMALY_DETECT_STD``, so at the threshold this
    returns exactly 0.5 and the graded path is a softening of the binary
    decision boundary rather than a different one. Width is
    ``config.GRADED_EVIDENCE_WIDTH`` (PROVISIONAL).
    """
    z = (ratio - config.ANOMALY_DETECT_STD) / config.GRADED_EVIDENCE_WIDTH
    if z < -700.0:  # avoid overflow on absurd inputs
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def score_segments_graded(
    residual_ratios: dict[PidName, float], epdg: EPDG
) -> list[Candidate]:
    """Score segments on graded evidence, best first.

    Generalises ``footprint_attribute`` in tests/test_generalization.py to
    non-binary evidence. For a segment with footprint F, and soft membership
    ``s_i`` per sensor:

        P(evidence | F) = PROD_{i in F}   [ p*s_i + (1-p)*(1-s_i) ]
                        * PROD_{j not in F} [ (1-s_j) ]

    with ``p = config.RAIL_MANIFEST_PROB``. A member either manifested (weight
    ``p``, and we then expect it elevated) or has not yet (weight ``1-p``, and
    we expect it quiet). A non-member is expected quiet, so an elevated sensor
    outside the footprint penalises the hypothesis.

    This reduces EXACTLY to the binary case: with every ``s_i`` in {0, 1} the
    member product becomes ``p^k (1-p)^(m-k)`` and any elevated non-member
    zeroes the hypothesis, which is the ``observed <= expected`` constraint.

    Scores are posteriors normalised to sum to 1 across candidates. That makes
    them comparable to the Jaccard scale for the margin test — it does NOT make
    them calibrated probabilities; the prior and the manifestation rate are both
    invented constants.
    """
    p = config.RAIL_MANIFEST_PROB
    universe = {n.id for n in epdg.nodes_of_kind(NodeKind.SENSOR)}
    soft = {
        pid: soft_membership(r)
        for pid, r in residual_ratios.items()
        if pid in universe
    }

    matrix = epdg.footprint_matrix()
    n_conn = sum(1 for s in matrix if s.startswith("SEG_CONN_")) or 1
    n_rail = sum(1 for s in matrix if s.startswith("SEG_RAIL_")) or 1

    raw: dict[SegmentId, float] = {}
    for segment_id, footprint in matrix.items():
        is_rail = segment_id.startswith("SEG_RAIL_")
        prior = (
            config.PRIOR_RAIL_FAULT / n_rail
            if is_rail
            else config.PRIOR_CONNECTOR_FAULT / n_conn
        )
        lik = 1.0
        for pid, s in soft.items():
            if pid in footprint:
                lik *= p * s + (1.0 - p) * (1.0 - s)
            else:
                lik *= 1.0 - s
        raw[segment_id] = prior * lik

    total = sum(raw.values())
    observed = frozenset(pid for pid, s in soft.items() if s >= 0.5)

    out: list[Candidate] = []
    for segment_id, footprint in matrix.items():
        out.append(
            Candidate(
                segment_id=segment_id,
                label=label_for_segment(segment_id),
                match_score=(raw[segment_id] / total) if total > 0 else 0.0,
                footprint=footprint,
                matched=footprint & observed,
                missing=footprint - observed,
                unexpected=observed - footprint,
            )
        )
    out.sort(key=lambda c: (-c.match_score, c.segment_id))
    return out


def score_segments(
    observed_anomalous: set[PidName], epdg: EPDG
) -> list[Candidate]:
    """Score every segment against the observation, best first.

    Ties break on segment id so the ranking is deterministic — without that, a
    collision could resolve differently between runs and the abstention in
    ``attribute`` would be unreproducible.
    """
    observed = frozenset(observed_anomalous)
    out: list[Candidate] = []
    for segment_id, footprint in epdg.footprint_matrix().items():
        out.append(
            Candidate(
                segment_id=segment_id,
                label=label_for_segment(segment_id),
                match_score=_jaccard(footprint, observed),
                footprint=footprint,
                matched=footprint & observed,
                missing=footprint - observed,
                unexpected=observed - footprint,
            )
        )
    out.sort(key=lambda c: (-c.match_score, c.segment_id))
    return out


# ---------------------------------------------------------------------------
# The attributor
# ---------------------------------------------------------------------------


def attribute(
    observed_anomalous: set[PidName],
    epdg: EPDG,
    tier1: Tier1Assessment,
    residual_ratios: Optional[dict[PidName, float]] = None,
) -> Attribution:
    """Attribute an observed anomaly set to a harness segment, or abstain.

    Follows spec §2 step for step. The candidate list is returned in every
    outcome, including both abstentions: the scores are what justify declining,
    and a reviewer reading the dashboard needs to see them.

    When ``config.USE_GRADED_EVIDENCE`` is on and ``residual_ratios`` is
    supplied, candidates are scored on graded evidence instead of the
    thresholded set. The binary path is unchanged and remains the default.
    """
    graded = config.USE_GRADED_EVIDENCE and residual_ratios is not None
    if graded:
        candidates = tuple(score_segments_graded(residual_ratios, epdg))
    else:
        candidates = tuple(score_segments(observed_anomalous, epdg))

    # Step 1 — Tier-1 confound. Absolute: no Tier-2 verdict is safe, regardless
    # of how cleanly some segment happens to fit. confidence is null rather than
    # the top score, because reporting a score here would invite reading it as a
    # weak answer when it is no answer at all.
    if tier1.tripped:
        return Attribution(
            origin_layer=None,
            segment_id=None,
            confidence=None,
            abstained=True,
            reason=REASON_TIER1_CONFOUND,
            candidates=candidates,
        )

    # Step 2/3 — discard hypotheses that do not clear the floor.
    if graded:
        # FOOTPRINT_MATCH_FLOOR is a set-agreement quantity and does not
        # transfer to a normalised posterior. The equivalent guard is
        # evidential: if no sensor is more likely elevated than not, there is
        # nothing to explain and every candidate is just its prior.
        sensors = {n.id for n in epdg.nodes_of_kind(NodeKind.SENSOR)}
        has_evidence = any(
            soft_membership(r) >= 0.5
            for pid, r in residual_ratios.items()  # type: ignore[union-attr]
            if pid in sensors
        )
        viable = candidates if has_evidence else ()
    else:
        viable = tuple(
            c for c in candidates if c.match_score >= config.FOOTPRINT_MATCH_FLOOR
        )
    if not viable:
        return Attribution(
            origin_layer=None,
            segment_id=None,
            confidence=None,
            abstained=True,
            reason=REASON_NO_SUPPORTED_HYPOTHESIS,
            candidates=candidates,
        )

    top = viable[0]

    # Step 3 — footprint collision. Two hypotheses this close cannot be told
    # apart by this observation. The score is retained: unlike the Tier-1 case
    # we do have a well-supported explanation, we just have more than one.
    if len(viable) >= 2:
        margin = top.match_score - viable[1].match_score
        if margin < config.TIER2_AMBIGUOUS_MARGIN:
            return Attribution(
                origin_layer=None,
                segment_id=None,
                confidence=top.match_score,
                abstained=True,
                reason=REASON_FOOTPRINT_COLLISION,
                candidates=candidates,
            )

    # PROTOTYPE step, off by default. If the winner's footprint is strictly
    # inside another viable candidate's, the observation cannot rule out the
    # larger segment having only partly manifested. The difference is always
    # explainable that way, because observed ⊆ winner ⊂ other means every extra
    # sensor is one we did not see move.
    if config.ABSTAIN_ON_NESTED_FOOTPRINT:
        observed = frozenset(observed_anomalous)
        nested_in = [
            c for c in viable
            if c.segment_id != top.segment_id and top.footprint < c.footprint
        ]
        if nested_in and observed <= top.footprint:
            return Attribution(
                origin_layer=None,
                segment_id=None,
                confidence=top.match_score,
                abstained=True,
                reason=REASON_NESTED_FOOTPRINT,
                candidates=candidates,
            )

    # Step 4 — a single best explanation.
    return Attribution(
        origin_layer=ORIGIN_LAYER_TIER2,
        segment_id=top.segment_id,
        confidence=top.match_score,
        abstained=False,
        reason=None,
        candidates=candidates,
    )
