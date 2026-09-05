"""
Adds src/ to sys.path before anything else in this package runs, so every
module here can import database/models/scoring/config the same flat way
runner.py and recalculate_scores.py already do. Package __init__ modules
run before any of their submodules, so this is guaranteed to happen first.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
