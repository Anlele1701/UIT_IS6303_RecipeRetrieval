import json
import shutil

import compare_a1


def fake_run(tmp_path, shift: float):
    run = tmp_path / "run"
    run.mkdir()
    shutil.copy(compare_a1.REFERENCE / "settings.json", run / "settings.json")
    metrics = json.loads((compare_a1.REFERENCE / "metrics.json").read_text(encoding="utf-8"))
    for m in metrics:
        if m["config"] == "hybrid":
            m["mrr"] += shift
    (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return run


def test_an_identical_run_matches(tmp_path):
    res = compare_a1.compare(fake_run(tmp_path, 0.0))
    assert res["match"] and set(res["configs"]) == {"fusion", "hybrid"}


def test_a_shift_beyond_the_tolerance_does_not_match(tmp_path):
    res = compare_a1.compare(fake_run(tmp_path, 0.02))
    assert not res["configs"]["hybrid"]["match"] and res["configs"]["fusion"]["match"]
    assert not res["match"]
