"""Only allow-listed content reaches a prompt (Thy, gate MV1; ADR-0006)."""

import json
from pathlib import Path

import pytest

from api.patient import ccda, rules
from api.patient.models import PatientNode
from api.patient.prompt_view import prompt_view, visible_facts
from api.patient.tree import build_tree

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"


@pytest.fixture(scope="module")
def rs():
    return rules.load_rules()


@pytest.fixture(scope="module")
def nodes(rs):
    return build_tree(ccda.read_record(FIXTURE, "sample", rs.p7)[0])


def node(nid, facts):
    return PatientNode(nid, "patient:p", "fixed", nid, None, facts, [])


def test_problems_only_when_a_nutrient_rule_names_them(rs):
    facts = [{"code": "59621000", "display": "Essential hypertension (disorder)"},
             {"code": "203646004", "display": "Adolescent idiopathic scoliosis (disorder)"},
             {"code": "80394007", "display": "Hyperglycemia (disorder)"}]  # unmapped row: not an allow-list entry
    assert visible_facts(node("problems.active", facts), rs) == [{"display": "Essential hypertension (disorder)"}]


def test_sample_allergies_show_only_the_food_ones(nodes, rs):
    shown = visible_facts(next(n for n in nodes if n.node_id == "allergies"), rs)
    assert sorted(f["substance"] for f in shown) == ["Shellfish (substance)", "Wheat (substance)"]  # not latex, mold...


def test_meds_only_when_a_drug_rule_matches(rs):
    facts = [{"display": "Simvastatin 20 MG Oral Tablet"}, {"display": "Fexofenadine hydrochloride 30 MG Oral Tablet"}]
    assert visible_facts(node("meds.active", facts), rs) == [{"display": "Simvastatin 20 MG Oral Tablet"}]


def test_vitals_only_allow_listed_codes(nodes, rs):
    shown = visible_facts(next(n for n in nodes if n.node_id == "vitals.latest"), rs)
    assert {f["display"] for f in shown} <= {"Body Weight", "Body Height", "Body mass index (BMI) [Ratio]",
                                             "Body Mass Index"}
    assert len(shown) == 3


def test_encounters_become_generic_classes(rs):
    facts = [{"code": "394701000", "display": "Asthma follow-up (regime/therapy)", "date": "2020-03-01"},
             {"code": "424619006", "display": "Prenatal visit (regime/therapy)", "date": "2020-05-02"},
             {"code": "999999", "display": "Something new", "date": "2020-06-03"}]
    shown = visible_facts(PatientNode("encounters.2020", "patient:p", "context", "Encounters 2020", None, facts, []), rs)
    assert shown == [{"class": "follow_up", "month": "2020-03"}, {"class": "wellness", "month": "2020-05"},
                     {"class": "other", "month": "2020-06"}]


def test_no_excluded_code_or_identity_in_any_view(nodes, rs):
    text = json.dumps([prompt_view(n, rs) for n in nodes])
    for code in [*rs.p7.exclude_loinc, *(c for _, c in rs.p7.exclude_codes)]:
        assert code not in text
    for word in ["Barton704", "Upton904", "Latex", "Allergic disorder", "scoliosis", "entry_id"]:
        assert word not in text, word
