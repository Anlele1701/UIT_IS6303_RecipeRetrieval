"""A patient's record as one Markdown document, and its heading tree. For the vectorless branch only.

`render` is deterministic and uses no LLM: the same rows always give the same text, so the true list of
active conditions is known (it is what the tables say) and the navigator can be scored against it.
The document is derived data. `/recommend` never reads it; it decides from the tables.

Layout (headings carry a `<!-- section_id: ... -->` line, which is what the navigator sees and picks):

    # Patient record: <name>
    ## Demographics
    ## Active conditions
    ## Resolved conditions
    ## Medications          (### Currently taking, ### Stopped)
    ## Allergies
    ## Laboratory and vitals (latest)
"""

import re
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import psycopg

from . import patients

SECTION_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SECTION_ID_RE = re.compile(r"^<!--\s*section_id:\s*([A-Za-z0-9_.-]+)\s*-->\s*$")


# ---------------------------------------------------------------------------
# Rows -> Markdown
# ---------------------------------------------------------------------------


@dataclass
class Record:
    patient_id: UUID
    display_name: str
    age: int
    gender: str
    reference_date: date
    conditions: list[tuple]  # code, description, start_date, stop_date
    medications: list[tuple]  # code, description, start, stop, reason_code, reason_description
    allergies: list[tuple]  # code, description, category, start_date, stop_date
    observations: list[tuple]  # code, description, observed_at, value, units


def fetch_record(conn: psycopg.Connection, patient_id: UUID | str) -> Record:
    """Everything the document is made of. Raises patients.PatientNotFound for an unknown id."""
    row = conn.execute(
        """SELECT p.id, p.display_name, p.birth_date, p.gender, r.reference_date
           FROM ehr.patient p JOIN ehr.cohort_run r USING (run_id) WHERE p.id = %s""", [str(patient_id)]).fetchone()
    if row is None:
        raise patients.PatientNotFound(str(patient_id))
    pid, name, birth, gender, ref = row
    q = lambda sql: conn.execute(sql, [str(patient_id)]).fetchall()  # noqa: E731
    return Record(
        pid, name, patients.age_on(birth, ref), gender, ref,
        q("SELECT code, description, start_date, stop_date FROM ehr.condition WHERE patient_id = %s"),
        q("SELECT code, description, start_at::date, stop_at::date, reason_code, reason_description "
          "FROM ehr.medication WHERE patient_id = %s"),
        q("SELECT code, description, category, start_date, stop_date FROM ehr.allergy WHERE patient_id = %s"),
        q("""SELECT DISTINCT ON (code) code, description, observed_at::date, coalesce(value_num::text, value_text), units
             FROM ehr.observation WHERE patient_id = %s ORDER BY code, observed_at DESC"""))


def _span(start: date, stop: date | None) -> str:
    return f"since {start}" if stop is None else f"{start} to {stop}"


def render(rec: Record) -> str:
    """The Markdown document. Rows are sorted and de-duplicated so the output is stable."""
    out: list[str] = []

    def section(level: int, title: str, section_id: str, lines: list[str], empty: str = "None recorded."):
        out.append(f"{'#' * level} {title}")
        out.append(f"<!-- section_id: {section_id} -->")
        out.extend(lines or [empty])
        out.append("")

    out += [f"# Patient record: {rec.display_name}", "<!-- section_id: record -->",
            f"<!-- patient_id: {rec.patient_id} -->", ""]
    section(2, "Demographics", "demographics", [
        f"- Age: {rec.age}", f"- Sex: {'female' if rec.gender == 'F' else 'male' if rec.gender == 'M' else rec.gender}",
        f"- Record date: {rec.reference_date}"])

    # A condition is active when any of its rows has no stop date, the same rule as patients.get_profile.
    active: dict[str, tuple[str, date]] = {}
    for code, desc, start, stop in sorted(rec.conditions, key=lambda r: (r[3] is not None, r[2], r[0])):
        if stop is None:
            prev = active.get(code)
            active[code] = (desc, min(start, prev[1]) if prev else start)
    section(2, "Active conditions", "active_conditions", [
        f"- {desc} [SNOMED {code}], {_span(since, None)}"
        for code, (desc, since) in sorted(active.items(), key=lambda kv: (kv[1][1], kv[0]))])

    resolved = sorted({(code, desc, start, stop) for code, desc, start, stop in rec.conditions if stop is not None},
                      key=lambda r: (r[3], r[2], r[0]), reverse=True)
    section(2, "Resolved conditions", "resolved_conditions", [
        f"- {desc} [SNOMED {code}], {_span(start, stop)}" for code, desc, start, stop in resolved])

    def med_line(m: tuple) -> str:
        code, desc, start, stop, rcode, rdesc = m
        why = f", for {rdesc} [SNOMED {rcode}]" if rdesc else ""
        return f"- {desc} [RxNorm {code}], {_span(start, stop)}{why}"
    meds = sorted(set(rec.medications), key=lambda m: (m[2], m[0], m[1]), reverse=True)
    out += ["## Medications", "<!-- section_id: medications -->", ""]
    section(3, "Currently taking", "medications_current", [med_line(m) for m in meds if m[3] is None])
    section(3, "Stopped", "medications_stopped", [med_line(m) for m in meds if m[3] is not None])

    alle = sorted(set(rec.allergies), key=lambda a: (a[4] is not None, a[3], a[0]))
    section(2, "Allergies", "allergies", [
        f"- {desc} [{code}] ({cat or 'unclassified'}), {_span(start, stop)}" for code, desc, cat, start, stop in alle])

    section(2, "Laboratory and vitals (latest)", "laboratory", [
        f"- {desc} [LOINC {code}]: {value}{' ' + units if units else ''} ({when})"
        for code, desc, when, value, units in sorted(rec.observations, key=lambda o: o[1])])
    return "\n".join(out).rstrip("\n") + "\n"


def render_patient(conn: psycopg.Connection, patient_id: UUID | str) -> str:
    return render(fetch_record(conn, patient_id))


# ---------------------------------------------------------------------------
# Markdown -> heading tree
# ---------------------------------------------------------------------------


@dataclass
class Section:
    section_id: str
    title: str
    level: int
    start_line: int  # 1-based, the heading line
    end_line: int  # 1-based, last line of this section including its sub-sections
    text: str  # the heading and everything under it, sub-sections included
    parent: str | None = None
    children: list[str] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return len(self.text)


def _slug(title: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "section"
    sid, n = base, 2
    while sid in taken:
        sid, n = f"{base}_{n}", n + 1
    return sid


def parse_tree(markdown: str) -> list[Section]:
    """The sections of a document in order, with their nesting. Headings inside code fences are text.

    A section's id is its `<!-- section_id: ... -->` comment when the line right under the heading has
    one, else a slug of the title. Ids are unique within a document.
    """
    lines = markdown.splitlines()
    heads: list[tuple[int, int, str]] = []  # line index, level, title
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else SECTION_RE.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2)))
    sections: list[Section] = []
    taken: set[str] = set()
    stack: list[Section] = []
    for n, (i, level, title) in enumerate(heads):
        end = len(lines)
        for j, lvl, _ in heads[n + 1:]:
            if lvl <= level:
                end = j
                break
        declared = SECTION_ID_RE.match(lines[i + 1]) if i + 1 < len(lines) else None
        sid = declared.group(1) if declared and declared.group(1) not in taken else _slug(title, taken)
        taken.add(sid)
        while stack and stack[-1].level >= level:
            stack.pop()
        sec = Section(sid, title, level, i + 1, end, "\n".join(lines[i:end]).rstrip("\n"),
                      stack[-1].section_id if stack else None)
        if stack:
            stack[-1].children.append(sid)
        stack.append(sec)
        sections.append(sec)
    return sections


def table_of_contents(sections: list[Section]) -> str:
    """What the navigator is shown instead of the document: one line per section, indented by depth."""
    return "\n".join(
        f"{'  ' * (s.level - 1)}- [{s.section_id}] {s.title} (lines {s.start_line}-{s.end_line}, {s.chars} chars)"
        for s in sections)


def read_sections(sections: list[Section], ids: list[str]) -> str:
    """The text of the chosen sections. A section already inside a chosen parent is not repeated."""
    chosen = set(ids)
    by_id = {s.section_id: s for s in sections}
    parts = []
    for sid in ids:
        s = by_id.get(sid)
        if s is None:
            continue
        p, covered = s.parent, False
        while p:
            if p in chosen:
                covered = True
                break
            p = by_id[p].parent
        if not covered and s.text not in parts:
            parts.append(s.text)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Ground truth, read from the same rows the document was made from
# ---------------------------------------------------------------------------


def active_condition_codes(rec: Record) -> set[str]:
    return {code for code, _, _, stop in rec.conditions if stop is None}


def resolved_only_condition_codes(rec: Record) -> set[str]:
    """Conditions that appear in the document but are not active: what a careless reader might wrongly report."""
    return {code for code, _, _, _ in rec.conditions} - active_condition_codes(rec)

