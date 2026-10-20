"""MV0: C-CDA reading rules (spec 2.2-2.3) on the one sample record, and the inventory's privacy (P7).
No DB, no Ollama."""

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from api.patient import ccda

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ["Barton704", "Upton904", "raceCode", "ethnicGroupCode"]


@pytest.fixture(scope="module")
def doc():
    return ccda.parse(FIXTURE)


@pytest.fixture(scope="module")
def today(doc):
    return ccda.record_date(doc)


def section(doc, code):
    return ccda.sections(doc)[code][0]


def test_header(doc, today):
    assert ccda.patient_id(doc) == "887e4b4e-a3e1-b573-4a16-38386d3e0b88"
    assert ccda.sex(doc) == "M"
    assert today == date(2026, 8, 25)  # the document's effectiveTime, not the clock
    assert ccda.age_years(doc, today) == 21


def test_sections_by_loinc(doc):
    s = ccda.sections(doc)
    for code in [ccda.ALLERGIES, ccda.MEDICATIONS, ccda.PROBLEMS, ccda.VITALS, ccda.RESULTS, ccda.ENCOUNTERS]:
        assert code in s


def test_eight_active_allergies_two_of_them_food(doc):
    allergies = ccda.allergies(section(doc, ccda.ALLERGIES))
    active = [a for a in allergies if a.active]
    assert len(active) == 8
    food = {a.substance_code: a.substance_display for a in active if a.kind_code == ccda.FOOD_ALLERGY}
    assert food == {"412071004": "Wheat (substance)", "735029006": "Shellfish (substance)"}


def test_allergy_evidence_fields(doc):
    wheat = next(a for a in ccda.allergies(section(doc, ccda.ALLERGIES)) if a.substance_code == "412071004")
    assert wheat.entry_id == "887e4b4e-a3e1-b573-e91f-98d891253e61"  # act/id/@root
    assert wheat.severity == "Moderate"
    assert "Eruption of skin (disorder)" in wheat.reactions


def test_two_medications_in_use(doc, today):
    meds = ccda.medications(section(doc, ccda.MEDICATIONS), today)
    active = [m.display for m in meds if m.active]
    assert len(active) == 2
    assert any("Fexofenadine" in m for m in active)
    assert any("Epinephrine" in m for m in active)
    stopped = [m.display for m in meds if not m.active]
    assert any("fluoride" in m for m in stopped)
    assert any("Acetaminophen" in m for m in stopped)


def test_med_rule_ignores_status_and_reads_high():
    from lxml import etree
    ns = 'xmlns="urn:hl7-org:v3"'
    def sa(high):
        return etree.fromstring(f'<substanceAdministration {ns}><statusCode code="completed"/>'
                                f'<effectiveTime><low value="20200101"/>{high}</effectiveTime></substanceAdministration>')
    today = date(2026, 8, 25)
    assert ccda.med_active(sa(""), today)
    assert ccda.med_active(sa('<high nullFlavor="UNK"/>'), today)
    assert ccda.med_active(sa('<high value="20261231"/>'), today)
    assert not ccda.med_active(sa('<high value="20200101"/>'), today)


def test_active_disorders_and_dropped_findings(doc):
    probs = [p for p in ccda.problems(section(doc, ccda.PROBLEMS)) if p.active]
    assert [p.display for p in probs if p.suffix == "disorder"] == ["Adolescent idiopathic scoliosis (disorder)"]
    dropped = {p.display for p in probs if p.suffix != "disorder"}
    assert {"Educated to high school level (finding)", "Part-time employment (finding)",
            "Stress (finding)"} <= dropped


def test_semantic_suffix():
    assert ccda.semantic_suffix("Medication review due (situation)") == "situation"
    assert ccda.semantic_suffix("Chronic kidney disease stage 3 (disorder)") == "disorder"
    assert ccda.semantic_suffix("Anemia") == ""


def test_latest_vital_per_loinc(doc):
    latest = ccda.latest_by_loinc(ccda.vitals(section(doc, ccda.VITALS)))
    weight = latest["29463-7"]
    assert weight.unit == "kg"
    assert weight.when == max(o.when for o in ccda.vitals(section(doc, ccda.VITALS)) if o.loinc == "29463-7")


def test_results_hold_screening_and_cbc(doc):
    codes = {o.loinc for o in ccda.organizers(section(doc, ccda.RESULTS))}
    assert {"89206-7", "55757-9", "69737-5", "82666-9", "72109-2"} <= codes  # PHQ-Teen, PHQ-2, GAD-7, DAST-10, AUDIT-C
    assert "58410-2" in codes  # CBC


def test_inventory_of_the_fixture_has_no_identity(tmp_path, monkeypatch):
    import patient_inventory as inv
    folder = tmp_path / "ccda"
    folder.mkdir()
    (folder / FIXTURE.name).write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr(inv, "OUT", tmp_path / "out")
    monkeypatch.setattr(inv, "rule_check", lambda: {"present": False})
    summary = inv.write(inv.scan(folder), folder)
    assert summary["parsed"] == 1 and summary["p8_candidates"]["food_allergy"] == 1
    text = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "out").iterdir())
    for word in [*IDENTITY, "887e4b4e-a3e1-b573-4a16-38386d3e0b88", FIXTURE.stem]:
        assert word not in text, word


def test_committed_inventory_has_no_identity():
    out = ROOT / "eval" / "patient_inventory"
    if not out.exists():
        pytest.skip("inventory not built")
    text = "".join(p.read_text(encoding="utf-8") for p in out.iterdir())
    text += (ROOT / "docs" / "patient_inventory.md").read_text(encoding="utf-8")
    for word in IDENTITY:
        assert word not in text, word


def _loinc(name):
    return list(csv.DictReader(open(ROOT / "data" / "rules" / name, encoding="utf-8")))


def test_include_and_exclude_loinc_do_not_overlap():
    include, exclude = _loinc("include_loinc.csv"), _loinc("exclude_loinc.csv")
    inc, exc = [r["loinc"] for r in include], [r["loinc"] for r in exclude]
    assert len(inc) == len(set(inc)) and len(exc) == len(set(exc))
    assert not set(inc) & set(exc)
    assert "69409-1" in exc  # death certificate is P7 (Thy, after MV0)
    assert "55405-5" not in inc  # heart failure: no rule yet


def test_exclude_loinc_covers_the_fixture_screening_organizers(doc):
    exc = {r["loinc"] for r in _loinc("exclude_loinc.csv")}
    inc = {r["loinc"] for r in _loinc("include_loinc.csv")}
    codes = {o.loinc for o in ccda.organizers(section(doc, ccda.RESULTS))}
    assert {"89206-7", "55757-9", "69737-5", "82666-9", "72109-2"} <= exc
    assert codes <= exc | inc  # the sample has only screening forms and a CBC


def test_inventory_groups_by_code_not_by_name():
    out = ROOT / "eval" / "patient_inventory"
    if not out.exists():
        pytest.skip("inventory not built")
    for name, key in [("organizers.csv", ["loinc"]), ("problems.csv", ["snomed_code"]),
                      ("medications.csv", ["rxnorm_code"]), ("allergies.csv", ["kind_code", "substance_code"]),
                      ("observations.csv", ["section", "organizer_loinc", "loinc"])]:
        rows = list(csv.DictReader(open(out / name, encoding="utf-8")))
        keys = [tuple(r[k] for k in key) for r in rows]
        assert len(keys) == len(set(keys)), name


def test_allergy_substance_draft_uses_known_groups():
    allowed = {"milk", "egg", "fish", "crustacean_shellfish", "tree_nuts", "peanut", "wheat", "soy", "sesame"}
    rows = list(csv.DictReader(open(ROOT / "data" / "rules" / "allergy_substance.csv", encoding="utf-8")))
    assert rows
    for r in rows:
        assert set(filter(None, r["allergens"].split(";"))) <= allowed, r
    summary = ROOT / "eval" / "patient_inventory" / "summary.json"
    if summary.exists():  # every food substance in the data has a row
        food = [r for r in csv.DictReader(open(ROOT / "eval" / "patient_inventory" / "allergies.csv", encoding="utf-8"))
                if r["kind_code"] == ccda.FOOD_ALLERGY]
        assert {r["substance_code"] for r in food} <= {r["snomed_code"] for r in rows}
        assert json.loads(summary.read_text(encoding="utf-8"))["parse_errors"] == []
