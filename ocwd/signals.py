"""Excitation signals (engine speed, vehicle speed) decoded from passive CAN.

The decoders below were identified for the three CANmodes vehicles by
searching every 16-bit field for smooth, wide-range signals and checking the
scaled values against physical ranges (idle ~750 rpm, highway ~2300 rpm and
80-110 km/h on the highway captures).  GM matches the public opendbc
definitions (ECMEngineStatus 0x0C9, ECMVehicleSpeed 0x3E9); VW matches the PQ
platform Motor_1 (0x280) and Bremse_1 (0x1A0) layouts.  The CAN-MIRGU vehicle
is undisclosed and has no decoder; the detector then falls back to its
excitation-free feature subset.

Signals are decoded only from frames that survived to the logger, exactly as
a deployed tool would see them.
"""
from __future__ import annotations

import numpy as np

# vehicle -> {"rpm": (id, byte_offset, endian, scale), "speed": (...)}
DECODERS = {
    "GM-Cruze": {"rpm": (0x0C9, 1, "be", 0.25), "speed": (0x3E9, 0, "be", 0.01 * 1.609344)},
    "VW-Gol": {"rpm": (0x280, 2, "le", 0.25), "speed": (0x1A0, 2, "le", 0.005)},
    # Hyundai/KIA EMS11 (0x316): engine speed bytes 2-3 LE x0.25, vehicle speed byte 6 (km/h)
    "KIA-Soul": {"rpm": (0x316, 2, "le", 0.25), "speed": (0x316, 6, "u8", 1.0)},
    # can-train-and-test vehicles (Lampe & Meng); layouts from the opendbc sheet shipped with the data
    "GM-Impala": {"rpm": (0x0C9, 1, "be", 0.25), "speed": (0x3E9, 0, "be", 0.01 * 1.609344)},
    "GM-Traverse": {"rpm": (0x0C9, 1, "be", 0.25), "speed": (0x3E9, 0, "be", 0.01 * 1.609344)},
    "GM-Silverado": {"rpm": (0x0C9, 1, "be", 0.25), "speed": (0x3E9, 0, "be", 0.01 * 1.609344)},
    "Subaru-Forester": {"rpm": (0x140, 2, "le14", 1.0), "speed": (0x0D1, 0, "le", 0.05625)},
    "Ford-Fiesta": {"rpm": (0x201, 0, "be", 1.0), "speed": (0x201, 4, "be", 0.01)},
}
LIMITS = {"rpm": (0.0, 8000.0), "speed": (0.0, 250.0)}


def has_decoder(vehicle: str) -> bool:
    return vehicle in DECODERS


def decode(vehicle: str, t: np.ndarray, can_id: np.ndarray, payload: np.ndarray, kind: str):
    """payload: (n, 8) uint8 array aligned with t / can_id."""
    if vehicle not in DECODERS:
        return np.zeros(0), np.zeros(0)
    cid, off, endian, scale = DECODERS[vehicle][kind]
    m = can_id == cid
    b = payload[m]
    if endian == "le14":
        raw = (b[:, off + 1].astype(np.float64) * 256 + b[:, off]) % 16384
    elif endian == "u8":
        raw = b[:, off].astype(np.float64)
    elif endian == "be":
        raw = b[:, off].astype(np.float64) * 256 + b[:, off + 1]
    else:
        raw = b[:, off + 1].astype(np.float64) * 256 + b[:, off]
    v = raw * scale
    lo, hi = LIMITS[kind]
    ok = (v >= lo) & (v <= hi)
    return t[m][ok], v[ok]


def payload_matrix(hexstrings) -> np.ndarray:
    out = np.zeros((len(hexstrings), 8), dtype=np.uint8)
    for i, s in enumerate(hexstrings):
        if not isinstance(s, str):
            continue
        n = min(len(s) // 2, 8)
        try:
            out[i, :n] = np.frombuffer(bytes.fromhex(s[: 2 * n]), dtype=np.uint8)
        except ValueError:
            pass
    return out
