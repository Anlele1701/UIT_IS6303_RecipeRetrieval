"""The record document: rendering from the ehr tables, parsing its heading tree, and the true answers."""

import re
from uuid import UUID

import pytest

from api import ehr_document, patients

P = {n: UUID(int=n) for n in range(1, 8)}


def doc(ehr, n):
    return ehr_document.render_patient(ehr, P[n])


def test_the_document_has_the_expected_sections_in_order(ehr):
    tree = ehr_document.parse_tree(doc(ehr, 1))
    assert [(s.section_id, s.level) for s in tree] == [
        ("record", 1), ("demographics", 2), ("active_conditions", 2), ("resolved_conditions", 2),
        ("medications", 2), ("medications_current", 3), ("medications_stopped", 3), ("allergies", 2),
        ("laboratory", 2)]
    assert [s.parent for s in tree][:3] == [None, "record", "record"]
    assert tree[4].children == ["medications_current", "medications_stopped"]


def test_active_and_resolved_conditions_are_in_their_own_sections(ehr):
    by = {s.section_id: s.text for s in ehr_document.parse_tree(doc(ehr, 3))}
    assert "[SNOMED 314529007], since 2026-01-01" in by["active_conditions"]
    assert "59621000" not in by["active_conditions"]  # the hypertension of patient 3 ended in 2015
    assert "[SNOMED 59621000], 2005-02-02 to 2015-02-02" in by["resolved_conditions"]


def test_a_patient_with_nothing_to_list_still_has_every_section(ehr):
    by = {s.section_id: s.text for s in ehr_document.parse_tree(doc(ehr, 4))}
    assert "None recorded." in by["resolved_conditions"] and "[735029006] (food)" in by["allergies"]


def test_rendering_is_deterministic(ehr):
    assert doc(ehr, 1) == doc(ehr, 1)


def test_the_document_agrees_with_the_profile_on_who_is_active(ehr):
    for n in (1, 2, 3, 4, 5, 7):
        tree = {s.section_id: s.text for s in ehr_document.parse_tree(doc(ehr, n))}
        in_doc = {c for c in re.findall(r"\[SNOMED (\d+)\]", tree["active_conditions"])}
        assert in_doc == {c.code for c in patients.get_profile(ehr, P[n]).active_conditions}


def test_ground_truth_comes_from_the_rows(ehr):
    rec = ehr_document.fetch_record(ehr, P[3])
    assert ehr_document.active_condition_codes(rec) == {"314529007"}
    assert ehr_document.resolved_only_condition_codes(rec) == {"59621000"}


def test_unknown_patient(ehr):
    with pytest.raises(patients.PatientNotFound):
        ehr_document.render_patient(ehr, UUID(int=999))


# --- the parser on its own --------------------------------------------------------------------

TEXT = """# Title
<!-- section_id: top -->
intro
## A
<!-- section_id: a -->
- one
### A1
- nested
## B
```
## not a heading
```
## A
<!-- section_id: a -->
- duplicate id
"""


def test_parse_tree_nests_numbers_lines_and_keeps_ids_unique():
    tree = ehr_document.parse_tree(TEXT)
    assert [(s.section_id, s.level, s.start_line, s.end_line, s.parent) for s in tree] == [
        ("top", 1, 1, 15, None), ("a", 2, 4, 8, "top"), ("a1", 3, 7, 8, "a"),  # a heading in a code fence is text
        ("b", 2, 9, 12, "top"), ("a_2", 2, 13, 15, "top")]  # the repeated id "a" is renamed
    assert tree[1].children == ["a1"] and tree[0].children == ["a", "b", "a_2"]


def test_read_sections_does_not_repeat_a_section_inside_a_chosen_parent():
    tree = ehr_document.parse_tree("# T\n## A\n- one\n### A1\n- nested\n## B\n- two\n")
    ids = [s.section_id for s in tree]
    a, a1 = ids[1], ids[2]
    text = ehr_document.read_sections(tree, [a, a1, "missing"])
    assert text.count("- nested") == 1 and "- two" not in text


def test_table_of_contents_shows_titles_and_sizes_but_no_content(ehr):
    d = doc(ehr, 1)
    toc = ehr_document.table_of_contents(ehr_document.parse_tree(d))
    assert "[active_conditions] Active conditions (lines " in toc and "chars)" in toc
    assert "Essential hypertension" not in toc
