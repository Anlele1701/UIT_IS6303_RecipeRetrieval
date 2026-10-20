"""Ingredient pipeline (rules D4-D8): parse raw lines, map them to canonical ingredients, tag Recipes."""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:  # `python -m lexicon.<tool>` from scripts/ still finds the api package
    sys.path.insert(0, _ROOT)
