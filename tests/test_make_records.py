"""Synthetic patient records: no DB, no network, no LLM."""

import json

import make_records as mr
from export_record_pdfs import export_one


def test_same_seed_same_markdown_and_answer_key(tmp_path):
    out = tmp_path / "records"
    written, skipped = mr.build_records(out, out / "answer_key.json", size=2, seed=603, force=True)
    assert written == 2 and skipped == []
    first = {p.name: p.read_text() for p in out.glob("p*.md")}
    key1 = json.loads((out / "answer_key.json").read_text())

    written2, skipped2 = mr.build_records(out, out / "answer_key.json", size=2, seed=603, force=True)
    assert written2 == 2
    second = {p.name: p.read_text() for p in out.glob("p*.md")}
    key2 = json.loads((out / "answer_key.json").read_text())
    assert first == second
    assert key1 == key2
    assert skipped2 == []


def test_idempotent_skip_without_force(tmp_path):
    out = tmp_path / "records"
    mr.build_records(out, out / "answer_key.json", size=2, seed=603)
    written, skipped = mr.build_records(out, out / "answer_key.json", size=2, seed=603)
    assert written == 0
    assert skipped == ["p001", "p002"]


def test_assert_catches_missing_value():
    current = [mr.Constraint(
        nutrient="sodium_mg", op="max", value=600, unit="mg",
        effective_date="2026-03-12", evidence_section_id="visit-2026-03-12-dietitian",
    )]
    md = "# Patient Record p001\n\n<!-- section_id: visit-2026-03-12-dietitian -->\n\nNo numbers here.\n"
    # pad to pass length if we only care about missing value — shorten MIN by checking message
    md = md + ("filler text. " * 400)
    problems = mr.assert_record(md, current, [])
    assert any("missing value text '600 mg'" in p for p in problems)


def test_assert_catches_missing_section_id():
    current = [mr.Constraint(
        nutrient="sodium_mg", op="max", value=600, unit="mg",
        effective_date="2026-03-12", evidence_section_id="visit-2026-03-12-dietitian",
    )]
    md = "# Patient Record p001\n\nmaximum 600 mg sodium per serving.\n" + ("x " * 2000)
    problems = mr.assert_record(md, current, [])
    assert any("missing section_id" in p for p in problems)


def test_generated_record_has_section_ids_and_values(tmp_path):
    out = tmp_path / "records"
    mr.build_records(out, out / "answer_key.json", size=1, seed=603, limit=1, force=True)
    key = json.loads((out / "answer_key.json").read_text())[0]
    md = (out / "p001.md").read_text()
    slugs = mr.heading_slugs(md)
    for c in key["constraints"] + key["superseded"]:
        assert f"{c['value']} {c['unit']}" in md
        assert c["evidence_section_id"] in slugs
    assert key["constraints"] and key["superseded"]
    assert len(md) >= mr.MIN_CHARS


def test_limit_runs_quickly(tmp_path):
    out = tmp_path / "records"
    written, _ = mr.build_records(out, out / "answer_key.json", size=40, seed=603, limit=2)
    assert written == 2
    assert sorted(p.stem for p in out.glob("p*.md")) == ["p001", "p002"]


def test_export_pdf_smoke(tmp_path):
    out = tmp_path / "records"
    mr.build_records(out, out / "answer_key.json", size=1, seed=603, limit=1)
    pdf = tmp_path / "p001.pdf"
    export_one(out / "p001.md", pdf)
    assert pdf.exists() and pdf.stat().st_size > 500
    # Comments must not break export; PDF binary should start with %PDF
    assert pdf.read_bytes()[:4] == b"%PDF"
