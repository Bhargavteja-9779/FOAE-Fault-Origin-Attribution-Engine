"""Dataset locations. Override the root with the OCWD_DATA environment variable."""
import os
from pathlib import Path

DATA = Path(os.environ.get("OCWD_DATA", Path(__file__).resolve().parent.parent / "data" / "raw"))
CANMODES = DATA / "canmodes-datasets"
MIRGU = DATA / "CAN-MIRGU"
HCRL = DATA / "CHD" / "x"
CTT = DATA / "can-dataset"
VED_DYN = DATA / "VED" / "dyn"
VED_STATIC = DATA / "VED" / "Data"
CACHE = DATA.parent / "cache"
ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
