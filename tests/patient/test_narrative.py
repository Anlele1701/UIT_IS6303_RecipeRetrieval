"""MV4c: the narrative input (section tables only) on the sample record."""

import re
from pathlib import Path

from api.patient import ccda, narrative, rules
from api.patient.prompt_view import prompt_view
from api.patient.tree import build_tree

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
NO_P7 = rules.P7Rules({}, {}, {})


def test_one_node_per_section_named_by_its_title():
    nodes, today = narrative.narrative_nodes(FIXTURE, rules.load_rules().p7)
    assert [n.node_id for n in nodes[1:]] == [nid for _, nid, _ in narrative.SECTIONS]
    assert nodes[1].title == "Allergies and Adverse Reactions" and nodes[1].summary == "8 rows"
    assert {n.kind for n in nodes[1:]} == {"fixed", "context"} and today == ccda.record_date(ccda.parse(FIXTURE)).isoformat()


def test_the_text_holds_no_code_and_no_status():
    rs = rules.load_rules()
    nodes, _ = narrative.narrative_nodes(FIXTURE, rs.p7)
    text = "\n".join(narrative.as_text(n) for n in nodes[1:])
    coded = build_tree(ccda.read_record(FIXTURE, "sample", rs.p7)[0])
    codes = {f.get(k) for n in coded for f in n.facts for k in ("code", "substance_code", "kind_code") if f.get(k)}
    assert codes and not any(c in text for c in codes)
    rows = [line for line in text.splitlines() if not line.startswith("## ") and line != "(no rows)"]
    assert all(re.fullmatch(r"(\d{4}-\d{2}-\d{2}|\?) -> (\d{4}-\d{2}-\d{2}|no end date): .+", r) for r in rows)
    # which allergy is a food allergy is left to the words
    assert "Wheat (substance)" in text and "Latex (substance)" in text


def test_p7_rows_are_dropped_before_the_text():
    sec = ccda.sections(ccda.parse(FIXTURE))[ccda.ENCOUNTERS][0]
    code = narrative.table_rows(sec)[0]["Code"].split()[-1]
    p7 = rules.P7Rules({}, {}, {("encounter", code): "test"})
    full = narrative.narrative_nodes(FIXTURE, NO_P7)[0][-1]
    cut = narrative.narrative_nodes(FIXTURE, p7)[0][-1]
    gone = sum(r["Code"].split()[-1] == code for r in narrative.table_rows(sec))
    assert gone and len(cut.facts) == len(full.facts) - gone


def test_latest_weight_is_the_newest_body_weight_row():
    nodes, _ = narrative.narrative_nodes(FIXTURE, NO_P7)
    w = narrative.latest_weight(nodes)
    rows = [f for f in nodes[4].facts if f["description"] == "Body Weight"]
    assert w["date"] == max(r["start"] for r in rows) and w["unit"] == "kg" and float(w["value"]) > 0


def test_prompt_view_splits_a_narrative_value_into_number_and_unit():
    nodes, _ = narrative.narrative_nodes(FIXTURE, NO_P7)
    facts = prompt_view(nodes[4], rules.load_rules())["facts"]
    weight = next(f for f in facts if f["description"] == "Body Weight")
    assert weight["unit"] == "kg" and float(weight["value"]) > 0 and weight["date"]
