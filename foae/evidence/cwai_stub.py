"""CW-AI output interface.

The real CW-AI connector-wear detector is a separately filed patent, treated
here as a black box. This stub generates CWAIOutput for a given Tier-1 wear
level so the confounder gate can be exercised.

The stub's observation noise matters: if CWAIOutput were a noiseless readout of
true wear, any test of `assess_tier1_confound` would be circular.
config.CWAI_NOISE represents the real detector's imperfection.
"""

from __future__ import annotations

import numpy as np

from foae import config
from foae.types import CWAIOutput, WearClass

# CWAI_NOISE now lives in config.py (handoff.md §5 Rule 1 corollary: it can
# change the Claim 1 gate result, so it belongs in the audit). Value unchanged:
# 0.15.


def generate(
    tier1_wear: float,
    rng: np.random.Generator,
    worn_pins: tuple[int, ...] | None = None,
) -> CWAIOutput:
    """Synthesise a CWAIOutput for a given true Tier-1 wear level in [0, 1]."""
    if worn_pins is None:
        worn_pins = (config.PIN_CAN_HIGH, config.PIN_CAN_LOW)

    err = np.abs(rng.normal(0.0, 0.02, size=config.NUM_PINS))
    for p in worn_pins:
        err[p - 1] = max(
            0.0, tier1_wear + rng.normal(0.0, config.CWAI_NOISE)
        )

    resistance = {
        p: max(0.0, tier1_wear * config.TIER1_FULL_DEGRADE_OHM
               + rng.normal(0.0, config.CWAI_NOISE * config.TIER1_FULL_DEGRADE_OHM))
        for p in worn_pins
    }

    if tier1_wear < 0.15:
        wc = WearClass.PRISTINE
    elif tier1_wear < 0.4:
        wc = WearClass.LIGHT
    elif tier1_wear < 0.7:
        wc = WearClass.MODERATE
    else:
        wc = WearClass.SEVERE

    return CWAIOutput(
        per_pin_error_vector=err,
        contact_resistance_ohm=resistance,
        wear_class=wc,
        uncertainty=float(config.CWAI_NOISE),
    )
