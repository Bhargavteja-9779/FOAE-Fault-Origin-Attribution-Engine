"""Perturbation-response signature library.

Signatures are expressed ONLY in terms the simulator can substantiate:
magnitude, on a named response channel, over a named sensor set.

Lag and polarity are deliberately absent. Both were measured across the two
identifiability experiments and neither discriminated (lag AUC 0.53-0.68,
polarity indistinguishable from chance for both fault classes). See
`foae.types.ProbeSignature` for the numbers and the reinstatement condition.

STATUS: the magnitude ranges below are placeholders. No signature library can
be populated with defensible values until the bench rig exists — every number
here would otherwise be a simulator artefact quoted as a measurement.
"""

from __future__ import annotations

from foae import config
from foae.types import ProbeSignature, ResponseChannel

# NOT POPULATED. Deliberately empty rather than filled with invented ranges:
# a signature library derived from the simulator that generated it proves
# nothing, and in a patent-facing artefact would misrepresent simulated values
# as characterised ones.
SIGNATURE_LIBRARY: dict[str, ProbeSignature] = {}


def match(
    response_magnitude: float,
    channel: ResponseChannel,
    responding_sensors: tuple[str, ...],
    library: dict[str, ProbeSignature] | None = None,
) -> tuple[str | None, float]:
    """Return (segment_id, score) for the best-matching signature.

    Returns (None, 0.0) when the library is empty, which is the current state.
    Callers must treat a None match as "no segment identified" and fall back to
    footprint-only inference — not as evidence of any particular segment.
    """
    lib = SIGNATURE_LIBRARY if library is None else library
    if not lib:
        return None, 0.0

    best_id, best_score = None, 0.0
    for seg_id, sig in lib.items():
        if sig.response_channel is not channel:
            continue
        if not set(responding_sensors) & set(sig.affected_sensors):
            continue
        low, high = sig.expected_magnitude_range
        if low <= response_magnitude <= high:
            score = 1.0
        else:
            edge = low if response_magnitude < low else high
            width = max(high - low, 1e-9)
            score = max(0.0, 1.0 - abs(response_magnitude - edge) / width)
        if score > best_score:
            best_id, best_score = seg_id, score

    if best_score < config.FOOTPRINT_MATCH_FLOOR:
        return None, best_score
    return best_id, best_score
