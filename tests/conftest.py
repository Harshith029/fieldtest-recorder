import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "ftr-reference"
for p in (ROOT / "demo", REF / "research", REF):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
warnings.filterwarnings("ignore")
