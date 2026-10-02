"""Tier-1 confounder gate — design.md Claim 1.

Tier-1 (the J1962 diagnostic transport) is common-mode: wear there degrades all
PIDs together and carries no per-sensor attribution signal. It is therefore not
evidence FOR any Tier-2 hypothesis — it is a reason to distrust all of them.

This module converts CW-AI output into a confound score and a gate decision.
"""

from __future__ import annotations

from enum import Enum

import numpy as np

from foae import config
from foae.types import CWAIOutput


class GateAction(str, Enum):
    PROCEED = "proceed"          # Tier-1 clean
    INFLATE = "inflate"          # degraded: attribute, but raise uncertainty
    ABSTAIN = "abstain"          # confounded: assert no Tier-2 origin


def assess_tier1_confound(cwai: CWAIOutput) -> float:
    """Confound score in [0, 1]. 0 = transport clean, 1 = fully confounded."""
    err = float(np.max(cwai.per_pin_error_vector))
    if cwai.contact_resistance_ohm:
        ohm = max(cwai.contact_resistance_ohm.values())
    else:
        ohm = 0.0
    r_norm = min(1.0, ohm / config.TIER1_FULL_DEGRADE_OHM)

    score = (
        config.TIER1_CONFOUND_W_PIN_ERROR * min(1.0, err)
        + config.TIER1_CONFOUND_W_RESISTANCE * r_norm
    )
    return float(np.clip(score, 0.0, 1.0))


def gate(confound: float) -> GateAction:
    if confound > config.TIER1_CONFOUND_THRESHOLD:
        return GateAction.ABSTAIN
    if confound < config.TIER1_CONFOUND_CLEAN_FLOOR:
        return GateAction.PROCEED
    return GateAction.INFLATE
