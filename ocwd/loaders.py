"""Loaders for the three public, real-vehicle datasets used in this study.

* CANmodes (Roque et al., WCNPS 2024): passive RAW CAN logs and OBD-II PID
  polling logs from a GM Cruze, Ford Fiesta and VW Gol G6 (highway + urban).
* CAN-MIRGU (Rajapaksha et al., VehicleSec 2024): candump benign log from a
  moving vehicle with microsecond timestamps.
* VED (Oh et al., IEEE T-ITS 2022): one year of OBD-II telemetry, 383 vehicles.

Every loader returns plain numpy/pandas objects with timestamps in seconds.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths
from .signals import payload_matrix


@dataclass
class FrameLog:
    """A passive CAN capture: one row per received frame."""
    name: str
    vehicle: str
    scenario: str
    t: np.ndarray          # seconds, float64, sorted
    can_id: np.ndarray     # int
    dlc: np.ndarray        # int
    resolution: float      # timestamp quantisation (s)
    payload: np.ndarray = None   # (n, 8) uint8
    meta: dict = field(default_factory=dict)


@dataclass
class PollLog:
    """An OBD-II polling capture: one row per diagnostic response (Mode 01)."""
    name: str
    vehicle: str
    scenario: str
    t: np.ndarray          # response timestamps (s)
    pid: np.ndarray        # PID number per response
    rpm: tuple             # (t, value) of decoded engine speed
    speed: tuple           # (t, value) of decoded vehicle speed
    resolution: float


# ---------------------------------------------------------------------------
# CANmodes timestamps are written by an MCP2515 logger as "<sec>.<ms>" with the
# millisecond field NOT zero-padded (".75" is 75 ms) and, in one file, with
# locale thousands separators ("1.728.720.282.150").  Parse them exactly.
# ---------------------------------------------------------------------------
def _parse_canmodes_ts(col: pd.Series) -> np.ndarray:
    s = col.astype(str).str.strip()
    parts = s.str.split(".")
    n = parts.str.len()
    out = np.full(len(s), np.nan)
    two = (n == 2).to_numpy()
    if two.any():
        p = parts[two]
        sec = p.str[0].astype(np.int64).to_numpy()
        ms = p.str[1].astype(np.int64).to_numpy()
        out[two] = sec + ms / 1000.0
    many = (n > 2).to_numpy()
    if many.any():
        joined = s[many].str.replace(".", "", regex=False).astype(np.int64).to_numpy()
        out[many] = joined / 1000.0
    return _unwrap_stale_seconds(out)


def _unwrap_stale_seconds(t: np.ndarray, max_gap: float = 5.0) -> np.ndarray:
    """Repair the logger's unsynchronised seconds field.

    The MCP2515 logger takes seconds from an RTC and milliseconds from a free
    running counter.  After the millisecond field wraps, the seconds field
    stays stale for up to one second, producing e.g. ``57.990 -> 57.003``
    where the true time is ``58.003``.  Each timestamp is therefore resolved
    to whichever of ``{t, t+1, t-1}`` continues the sequence monotonically;
    if none does within ``max_gap`` it is left as-is (a session break).
    """
    out = t.copy()
    prev = out[0]
    for i in range(1, len(out)):
        x = out[i]
        best = x
        bestd = np.inf
        for c in (x, x + 1.0, x - 1.0):
            d = c - prev
            if -0.0015 <= d <= max_gap and d < bestd:
                best, bestd = c, d
        if bestd == np.inf:
            best = x
        out[i] = best
        prev = best
    return out


def _read_canmodes_csv(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, sep=";", dtype=str, on_bad_lines="skip")
    n0 = len(d)
    # Drop repeated header rows and rows the logger corrupted (non-hex IDs,
    # non-numeric timestamps).  The count is kept for the data statement.
    ok = d["ID"].astype(str).str.fullmatch(r"[0-9A-Fa-f]{1,8}") & \
        d["TimestampEpoch"].astype(str).str.fullmatch(r"[0-9]+(\.[0-9]+)+")
    d = d[ok.fillna(False)].copy()
    d.attrs["dropped_rows"] = n0 - len(d)
    d["t"] = _parse_canmodes_ts(d["TimestampEpoch"])
    d = d[np.isfinite(d["t"])]
    d["can_id"] = d["ID"].apply(lambda x: int(x, 16))
    d["dlc"] = pd.to_numeric(d["DLC"], errors="coerce").fillna(8).astype(int)
    return d


def _vehicle_of(name: str) -> str:
    n = name.lower()
    if "cruze" in n:
        return "GM-Cruze"
    if "fiesta" in n:
        return "Ford-Fiesta"
    if "gol" in n:
        return "VW-Gol"
    return "unknown"


def canmodes_raw_logs() -> list[FrameLog]:
    logs = []
    for sub, scen in [("RAW Logs - Highway", "highway"), ("RAW Logs - UrbanTraffic and Parking", "urban")]:
        files = sorted((paths.CANMODES / sub).glob("*.csv"))
        # The GM urban capture is split in two consecutive files; they are separate drives.
        for f in files:
            d = _read_canmodes_csv(f)
            logs.append(FrameLog(
                name=f.stem, vehicle=_vehicle_of(f.stem), scenario=scen,
                t=d["t"].to_numpy(), can_id=d["can_id"].to_numpy(), dlc=d["dlc"].to_numpy(),
                resolution=1e-3, payload=payload_matrix(d["DataBytes"].tolist()),
                meta={"dropped_rows": d.attrs.get("dropped_rows", 0)}))
    return logs


_PID_RE = re.compile(r"S01PID([0-9A-F]{2})_")


def canmodes_obd_logs() -> list[PollLog]:
    """OBD-II polling logs. Timestamps come from the raw file, decoded values
    from the companion *decoded* file (same row order)."""
    logs = []
    pairs = [
        ("OBD Logs - Highway", "highway", "LOG0934-Ford-Fiesta-OBD-Pids-80km", "decoded_LOG0934-Ford-Fiesta-OBD-Pids-80km"),
        ("OBD Logs - Highway", "highway", "LOG1335-GM-Cruze-OBD-Pids-40km", "decoded_LOG1335-GM-Cruze-OBD-Pids-40km"),
        ("OBD Logs - Highway", "highway", "LOG1646-VW-GOL-OBD-Pids-40km", "decoded_LOG1646-VW-GOL-OBD-Pids-40km"),
        ("OBD Logs - UrbanTraffic and Parking", "urban", "FORD-FIESTA-LOG1542-2247-OBD-Pids-Urban", "FORD-FIESTA-LOG1542-2247-OBD-Pids-Urban-Decoded"),
        ("OBD Logs - UrbanTraffic and Parking", "urban", "GM-CRUZE-LOG1129-2254-OBD-Pids-Urban", "GM-CRUZE-LOG1129-2254-OBD-Pids-Urban-Decoded"),
        ("OBD Logs - UrbanTraffic and Parking", "urban", "VW-GOL-LOG0806-2338-OBD-Pids-Urban", "VW-GOL-LOG0806-2338-OBD-Pids-Urban-Decoded"),
    ]
    for sub, scen, raw, dec in pairs:
        r = _read_canmodes_csv(paths.CANMODES / sub / f"{raw}.csv")
        r = r[r["can_id"] == 0x7E8].copy()       # engine ECU responses
        r["pid"] = r["DataBytes"].str[4:6].apply(lambda x: int(x, 16) if isinstance(x, str) and len(x) == 2 else -1)
        r = r[r["DataBytes"].str[2:4] == "41"]   # positive Mode-01 responses only
        rpm_m = r["pid"] == 0x0C
        spd_m = r["pid"] == 0x0D
        db = r["DataBytes"]
        rpm_v = db[rpm_m].apply(lambda x: (int(x[6:8], 16) * 256 + int(x[8:10], 16)) / 4.0).to_numpy()
        spd_v = db[spd_m].apply(lambda x: float(int(x[6:8], 16))).to_numpy()
        logs.append(PollLog(
            name=raw, vehicle=_vehicle_of(raw), scenario=scen,
            t=r["t"].to_numpy(), pid=r["pid"].to_numpy(),
            rpm=(r["t"][rpm_m].to_numpy(), rpm_v), speed=(r["t"][spd_m].to_numpy(), spd_v),
            resolution=1e-3))
    return logs


def mirgu_benign() -> list[FrameLog]:
    out = []
    for f in sorted(paths.MIRGU.rglob("Benign*.log")):
        t, ids, dl, pl = [], [], [], []
        with open(f, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                p = line.split()
                if len(p) < 3:
                    continue
                t.append(float(p[0].strip("()")))
                cid, data = p[2].split("#")
                ids.append(int(cid, 16))
                dl.append(len(data) // 2)
                pl.append(data)
        out.append(FrameLog(name=f.stem, vehicle="MIRGU-car", scenario="mixed",
                            t=np.asarray(t), can_id=np.asarray(ids), dlc=np.asarray(dl), resolution=1e-6,
                            payload=payload_matrix(pl)))
    return out


def _hcrl_parse(path: Path):
    """HCRL Car-Hacking CSV: Timestamp,ID,DLC,DATA0..DATA{DLC-1},Flag (R/T)."""
    t, ids, dl, pl, att = [], [], [], [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            p = line.rstrip().split(",")
            if len(p) < 4:
                continue
            try:
                n = int(p[2])
                t.append(float(p[0]))
                ids.append(int(p[1], 16))
            except ValueError:
                continue
            dl.append(n)
            pl.append("".join(x.zfill(2) for x in p[3:3 + n]))
            att.append(p[-1] == "T")
    return np.asarray(t), np.asarray(ids), np.asarray(dl), pl, np.asarray(att)


def hcrl_normal(min_dur: float = 60.0, margin: float = 1.0) -> list[FrameLog]:
    """Benign traffic of the HCRL Car-Hacking dataset (KIA Soul): the
    attack-free normal_run capture, plus every attack-free stretch of the four
    attack captures with ``margin`` seconds trimmed around injected frames."""
    out = []
    f = paths.HCRL / "normal_run_data.txt"
    t, ids, dl, pl = [], [], [], []
    with open(f, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            p = line.split()
            if len(p) < 7:
                continue
            t.append(float(p[1]))
            ids.append(int(p[3], 16))
            n = int(p[6])
            dl.append(n)
            pl.append("".join(p[7:7 + n]))
    out.append(FrameLog("HCRL-normal_run", "KIA-Soul", "mixed", np.asarray(t), np.asarray(ids),
                        np.asarray(dl), 1e-6, payload_matrix(pl)))
    seen = set()
    for name in ["DoS_dataset", "Fuzzy_dataset", "gear_dataset", "RPM_dataset"]:
        t, ids, dl, pl, att = _hcrl_parse(paths.HCRL / f"{name}.csv")
        P = payload_matrix(pl)
        ta = t[att]
        edges = np.r_[t[0] - margin, ta, t[-1] + margin]
        for k, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
            lo, hi = a + margin, b - margin
            if hi - lo < min_dur:
                continue
            m = (t >= lo) & (t <= hi) & ~att
            key = round(float(t[m][0]), 1)
            if key in seen:      # the four attack files share one normal block
                continue
            seen.add(key)
            out.append(FrameLog(f"HCRL-{name}#c{k}", "KIA-Soul", "mixed", t[m], ids[m], dl[m], 1e-6, P[m]))
    return out


def _session_bounds(t: np.ndarray, max_gap: float, min_dur: float) -> list[tuple[int, int]]:
    """Split a capture (in file/arrival order) into contiguous sessions.

    The CANmodes files concatenate many recording sessions days apart and
    contain occasional corrupted timestamps.  A session boundary is any
    backwards step or any forward gap above ``max_gap``; sessions shorter
    than ``min_dur`` seconds are discarded.  Gaps below ``max_gap`` are real
    in-session telemetry and are kept -- they are the natural false-alarm
    floor of a healthy installation.
    """
    dt = np.diff(t)
    cut = np.flatnonzero((dt < 0) | (dt > max_gap)) + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(t)]
    return [(a, b) for a, b in zip(starts, ends) if b - a > 10 and t[b - 1] - t[a] >= min_dur]


def frame_sessions(log: FrameLog, max_gap: float = 5.0, min_dur: float = 120.0) -> list[FrameLog]:
    out = []
    for k, (a, b) in enumerate(_session_bounds(log.t, max_gap, min_dur)):
        out.append(FrameLog(f"{log.name}#s{k}", log.vehicle, log.scenario,
                            log.t[a:b].copy(), log.can_id[a:b].copy(), log.dlc[a:b].copy(),
                            log.resolution, log.payload[a:b].copy(), {"parent": log.name}))
    return out


def poll_sessions(log: PollLog, max_gap: float = 5.0, min_dur: float = 120.0) -> list[PollLog]:
    out = []
    rt, rv = log.rpm
    st, sv = log.speed
    for k, (a, b) in enumerate(_session_bounds(log.t, max_gap, min_dur)):
        t0, t1 = log.t[a], log.t[b - 1]
        mr = (rt >= t0) & (rt <= t1)
        ms = (st >= t0) & (st <= t1)
        if mr.sum() < 5 or ms.sum() < 5:
            continue
        out.append(PollLog(f"{log.name}#s{k}", log.vehicle, log.scenario,
                           log.t[a:b].copy(), log.pid[a:b].copy(),
                           (rt[mr], rv[mr]), (st[ms], sv[ms]), log.resolution))
    return out


# ---------------------------------------------------------------------------
# VED
# ---------------------------------------------------------------------------
VED_COLS = {"DayNum": "day", "VehId": "veh", "Trip": "trip", "Timestamp(ms)": "ts_ms",
            "Vehicle Speed[km/h]": "speed", "Engine RPM[RPM]": "rpm", "MAF[g/sec]": "maf",
            "Absolute Load[%]": "load"}


def ved_frames(cache: bool = True) -> pd.DataFrame:
    """All VED dynamic records, reduced to the columns used here (cached as parquet)."""
    cp = paths.CACHE / "ved_reduced.parquet"
    if cache and cp.exists():
        return pd.read_parquet(cp)
    parts = []
    for f in sorted(paths.VED_DYN.glob("VED_*_week.csv")):
        d = pd.read_csv(f, usecols=list(VED_COLS))
        d = d.rename(columns=VED_COLS)
        parts.append(d.astype({"veh": "int32", "trip": "int32", "ts_ms": "int64",
                               "speed": "float32", "rpm": "float32", "maf": "float32",
                               "load": "float32", "day": "float64"}))
    d = pd.concat(parts, ignore_index=True)
    d = d.sort_values(["veh", "trip", "ts_ms"], kind="stable").reset_index(drop=True)
    if cache:
        paths.CACHE.mkdir(parents=True, exist_ok=True)
        d.to_parquet(cp)
    return d


def ved_static() -> pd.DataFrame:
    a = pd.read_excel(paths.VED_STATIC / "VED_Static_Data_ICE&HEV.xlsx")
    b = pd.read_excel(paths.VED_STATIC / "VED_Static_Data_PHEV&EV.xlsx")
    s = pd.concat([a, b], ignore_index=True)
    s = s.rename(columns={"VehId": "veh", "Vehicle Type": "type"})
    return s


def all_frame_sessions(cache: bool = True) -> list[FrameLog]:
    """Every passive session from CANmodes RAW and CAN-MIRGU (cached)."""
    import pickle
    cp = paths.CACHE / "frame_sessions.pkl"
    if cache and cp.exists():
        with open(cp, "rb") as fh:
            return pickle.load(fh)
    out = []
    seen = set()
    for L in canmodes_raw_logs() + mirgu_benign() + hcrl_normal():
        for S in frame_sessions(L):
            # the HCRL attack files embed the same benign block; keep one copy
            key = (S.vehicle, round(float(S.t[0]), 1), round(float(S.t[-1]), 1))
            if key in seen:
                continue
            seen.add(key)
            out.append(S)
    if cache:
        paths.CACHE.mkdir(parents=True, exist_ok=True)
        with open(cp, "wb") as fh:
            pickle.dump(out, fh)
    return out


def all_poll_sessions(cache: bool = True) -> list[PollLog]:
    import pickle
    cp = paths.CACHE / "poll_sessions.pkl"
    if cache and cp.exists():
        with open(cp, "rb") as fh:
            return pickle.load(fh)
    out = []
    for L in canmodes_obd_logs():
        out += poll_sessions(L)
    if cache:
        paths.CACHE.mkdir(parents=True, exist_ok=True)
        with open(cp, "wb") as fh:
            pickle.dump(out, fh)
    return out
