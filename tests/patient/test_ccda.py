"""MV1: read_record applies P2-P7 to the sample record (spec section 8). No DB, no Ollama."""

import json
from pathlib import Path

import pytest

from api.patient import ccda, rules

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
IDENTITY = ["Barton704", "Upton904", "raceCode", "ethnicGroupCode", "streetAddressLine"]


@pytest.fixture(scope="module")
def p7():
    return rules.load_p7()


@pytest.fixture(scope="module")
def read(p7):
    return ccda.read_record(FIXTURE, "sample", p7)


def test_header_fields(read):
    record, _ = read
    assert record.patient_id == "887e4b4e-a3e1-b573-4a16-38386d3e0b88"
    assert (record.source, record.sex, record.age_years, record.deceased) == ("sample", "M", 21, False)


def test_p2_p3_allergies_in_force_and_food(read):
    record, counts = read
    assert len(record.allergies) == 8
    food = {a.substance_code for a in record.allergies if a.kind_code == ccda.FOOD_ALLERGY}
    assert food == {"412071004", "735029006"}  # wheat, shellfish
    assert counts["P3"]["food_allergies"] == 2


def test_p4_only_disorders(read):
    record, counts = read
    assert [p.display for p in record.problems] == ["Adolescent idiopathic scoliosis (disorder)"]
    assert counts["P4"]["dropped_suffix_finding"] == 3  # educated to high school, part-time employment, stress


def test_p5_medications_in_use(read):
    record, counts = read
    names = [m.display for m in record.medications]
    assert len(names) == 2 and any("Fexofenadine" in n for n in names) and any("Epinephrine" in n for n in names)
    assert counts["P5"] == {"dropped_not_in_use": 6, "in_use": 2}


def test_p6_latest_vitals_one_per_loinc(read):
    record, _ = read
    codes = [o.loinc for o in record.vitals]
    assert len(codes) == len(set(codes)) and "29463-7" in codes


def test_p7_only_allow_listed_organizers_kept(read, p7):
    record, counts = read
    assert [o.loinc for o in record.results] == ["58410-2"]  # CBC
    assert counts["P7"]["organizer_mental_health"] == 11  # PHQ-Teen, PHQ-2, GAD-7
    assert counts["P7"]["organizer_substance_use"] == 3  # DAST-10 x2, AUDIT-C
    assert not {o.loinc for o in record.results} & set(p7.exclude_loinc)


def test_p7_dropped_sections_counted(read):
    _, counts = read
    assert counts["P7"]["section_29762-2_entries"] == 1  # Social History
    assert counts["P7"]["section_47420-5_entries"] == 14  # Functional Status


def test_record_holds_no_identity(read):
    record, counts = read
    text = json.dumps(record.to_dict(), default=str) + json.dumps(counts)
    for word in IDENTITY:
        assert word not in text, word


def test_exclude_codes_drop_problems_meds_and_encounters(p7):
    assert p7.excluded("problem", "6525002") == "substance_use"
    assert p7.excluded("encounter", "308646001") == "death"
    assert p7.excluded("medication", "351266") == "substance_use"
    assert p7.excluded("problem", "59621000") is None  # hypertension stays


def test_rules_refuse_overlapping_lists(tmp_path):
    for name in rules.P7_FILES:
        (tmp_path / name).write_bytes((rules.RULES_DIR / name).read_bytes())
    with open(tmp_path / "include_loinc.csv", "a", encoding="utf-8") as f:
        f.write("69409-1,death,x,true,v1\n")
    with pytest.raises(rules.RuleError, match="both"):
        rules.load_p7(tmp_path)
