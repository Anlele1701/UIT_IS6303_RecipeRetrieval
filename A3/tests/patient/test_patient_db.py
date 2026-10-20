"""MV1: patient_ingest.py on the throwaway test DB (tests/conftest.py; skipped without the container)."""

from pathlib import Path

import pytest

import patient_ingest as pi

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"
PID = "887e4b4e-a3e1-b573-4a16-38386d3e0b88"


@pytest.fixture
def patients(db):
    db.execute("TRUNCATE patient CASCADE")
    return db


def folder_with(tmp_path, name, *files):
    d = tmp_path / name
    d.mkdir()
    for f in files:
        (d / f.name).write_bytes(f.read_bytes())
    return d


def test_load_twice_keeps_one_row_and_its_source(patients, tmp_path):
    d = folder_with(tmp_path, "sample", FIXTURE)
    for _ in range(2):
        pi.cmd_load(patients, [(d, "sample")])
    rows = patients.execute("SELECT patient_id, source, deceased, sex FROM patient").fetchall()
    assert rows == [(PID, "sample", False, "M")]
    kinds = dict(patients.execute("SELECT kind, count(*) FROM patient_node GROUP BY kind").fetchall())
    assert kinds["root"] == 1 and kinds["fixed"] == 4 and kinds["context"] > 0
    assert patients.execute("SELECT count(*) FROM patient_node WHERE kind = 'context' AND summary_source = 'template'"
                            ).fetchone()[0] == kinds["context"]


def test_same_patient_in_two_folders_is_refused(patients, tmp_path):
    a = folder_with(tmp_path, "a", FIXTURE)
    b = folder_with(tmp_path, "b", FIXTURE)
    with pytest.raises(pi.DuplicatePatient):
        pi.cmd_load(patients, [(a, "sample"), (b, "generated")])
    pi.cmd_load(patients, [(a, "sample")])
    with pytest.raises(pi.DuplicatePatient):  # already loaded from another folder
        pi.cmd_load(patients, [(b, "generated")])
    assert patients.execute("SELECT source FROM patient").fetchall() == [("sample",)]


def test_a_broken_file_is_listed_not_fatal(patients, tmp_path):
    d = folder_with(tmp_path, "sample", FIXTURE)
    (d / "broken.xml").write_text("<not-ccda/>", encoding="utf-8")
    out = pi.cmd_load(patients, [(d, "sample")])
    assert out["patients"] == 1 and len(out["errors"]) == 1
    assert "broken" not in str(out["errors"])  # listed by hash, never by file name


def test_death_certificate_marks_deceased(patients, tmp_path):
    text = FIXTURE.read_text(encoding="utf-8")
    death = ('<entry><organizer classCode="BATTERY" moodCode="EVN"><id root="d1"/>'
             '<code code="69409-1" displayName="U.S. standard certificate of death"/>'
             '<effectiveTime value="20260801"/></organizer></entry>')
    marker = '<code code="30954-2"'
    i = text.index("<entry", text.index(marker))
    d = tmp_path / "sample"
    d.mkdir()
    (d / "p.xml").write_text(text[:i] + death + text[i:], encoding="utf-8")
    pi.cmd_load(patients, [(d, "sample")])
    assert patients.execute("SELECT deceased FROM patient").fetchone()[0] is True
    facts = str(patients.execute("SELECT facts FROM patient_node").fetchall())
    assert "69409-1" not in facts  # P7: counted, never stored
