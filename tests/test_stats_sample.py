import pytest

import make_allergen_sample as mas
from stats import rate, wilson


@pytest.mark.parametrize("k,n,lo,hi", [
    (8, 10, 0.4902, 0.9433),   # textbook values
    (0, 10, 0.0, 0.2775),
    (10, 10, 0.7225, 1.0),
    (50, 100, 0.4038, 0.5962),
])
def test_wilson_matches_reference_values(k, n, lo, hi):
    a, b = wilson(k, n)
    assert (round(a, 4), round(b, 4)) == (lo, hi)


def test_rate_handles_an_empty_denominator():
    assert rate(0, 0) == {"k": 0, "n": 0, "value": None, "ci95": None}


def test_allocation_is_proportional_and_sums_to_the_total():
    alloc = mas.allocate({"a": 500, "b": 300, "c": 199, "d": 1}, 200)
    assert sum(alloc.values()) == 200 and alloc == {"a": 100, "b": 60, "c": 40, "d": 0}


def fake_categories():
    return {f"cat{i}": list(range(i * 1000, i * 1000 + 50 + 37 * i)) for i in range(8)}


def test_the_sample_is_reproducible_stratified_and_has_a_stratified_holdout():
    rows = mas.draw(fake_categories())
    assert rows == mas.draw(fake_categories())
    assert len(rows) == 200 and len({r["recipe_id"] for r in rows}) == 200
    assert sum(r["split"] == "holdout" for r in rows) == 50
    assert sorted(r["sample_order"] for r in rows) == list(range(1, 201))
    per_cat = {}
    for r in rows:
        per_cat.setdefault(r["category"], [0, 0])
        per_cat[r["category"]][r["split"] == "holdout"] += 1
    for dev, held in per_cat.values():  # each category keeps about a quarter in the holdout
        assert abs(held - (dev + held) / 4) <= 1


def test_the_script_refuses_to_overwrite(tmp_path, monkeypatch):
    out = tmp_path / "allergen_sample.csv"
    out.write_text("already labeled")
    monkeypatch.setattr(mas, "OUT", out)
    monkeypatch.setattr("sys.argv", ["make_allergen_sample.py"])
    with pytest.raises(SystemExit, match="exists"):
        mas.main()
    assert out.read_text() == "already labeled"
