"""Without a patient_id the pipeline decides exactly as before MV3 (spec 8, test_no_patient_regression). Slow.

eval/mv3_regression_baseline.json was taken by scripts/regression_snapshot.py at commit 687da10, before any MV3
change to the pipeline. The same run now must give the same intents, routes, constraints, notices and Recipe ids in
order. The constraints event gained two keys for patient sessions (nutrient_limits, nutrient_soft); without a patient
they must be empty.
"""

import json
from pathlib import Path

import httpx
import pytest

from api import config

pytestmark = pytest.mark.slow
ROOT = Path(__file__).resolve().parent.parent
NEW_KEYS = {"nutrient_limits", "nutrient_soft"}


def test_no_patient_turns_match_the_pre_mv3_baseline():
    try:
        httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Ollama is not running")
    import regression_snapshot
    base = json.loads((ROOT / "eval" / "mv3_regression_baseline.json").read_text(encoding="utf-8"))
    got = regression_snapshot.run()
    assert len(got) == len(base)
    for g, b in zip(got, base):
        assert {k: g["constraints"][k] for k in NEW_KEYS} == {k: {} for k in NEW_KEYS}, g["message"]
        g = {**g, "constraints": {k: v for k, v in g["constraints"].items() if k not in NEW_KEYS}}
        assert g == b, b["message"]
