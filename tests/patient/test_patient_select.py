"""MV4a: strata from the rule codes, and the seeded top-up selection (no DB, no model)."""

from dataclasses import replace
from pathlib import Path

import pytest

import patient_select as ps
from api.patient import ccda, rules
from api.patient.models import Problem

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"


@pytest.fixture(scope="module")
def rs():
    return rules.load_rules()


@pytest.fixture(scope="module")
def codes(rs):
    return ps.condition_codes(rs)


@pytest.fixture(scope="module")
def base(rs):
    return ccda.read_record(FIXTURE, "generated", rs.p7)[0]


def with_problems(record, *codes_):
    probs = tuple(Problem(f"p{c}", c, f"x {c} (disorder)", "disorder", True) for c in codes_)
    return replace(record, problems=probs, allergies=())


def test_strata_come_from_the_rule_codes(codes, base):
    assert codes["59621000"] == "hypertension" and codes["90781000119102"] == "diabetes"
    assert codes["431855005"] == "ckd" and "80394007" not in codes  # hyperglycemia: an unmapped row, no stratum
    assert ps.strata(base, codes) == {"food_allergy"}  # wheat and shellfish, no rule condition
    assert ps.strata(with_problems(base, "44054006", "433144002"), codes) == {"diabetes", "ckd", "multi"}


def test_selection_tops_up_only_short_strata_deterministically(codes, base):
    pool = [(Path(f"d{i}.xml"), with_problems(base, "44054006")) for i in range(30)]
    pool += [(Path(f"h{i}.xml"), with_problems(base, "59621000")) for i in range(30)]
    pool += [(Path(f"x{i}.xml"), replace(with_problems(base, "44054006"), deceased=True)) for i in range(5)]
    have = {"diabetes": 10, "ckd": 15, "multi": 15}
    chosen, after = ps.select(pool, have, codes, target=15)
    assert after["diabetes"] == 15 and len(chosen) == 5
    assert all(p.name.startswith("d") for p, _ in chosen)  # hypertension-only and deceased ones are never taken
    assert ps.select(pool, have, codes, target=15)[0] == chosen  # same seed, same picks
