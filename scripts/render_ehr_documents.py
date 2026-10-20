"""Render every patient's record as a Markdown document into ehr.record_document, and report how long they are.

    python scripts/render_ehr_documents.py            # render all, then print the length distribution
    python scripts/render_ehr_documents.py --stats    # only print it, from what is stored

The documents are derived from the ehr tables (api/ehr_document.py), so this can be run again at any time.
The length report matters: tree navigation shows its value on long documents, and a record rendered from a
table is shorter and tidier than a real clinical note. The numbers say whether the comparison means much.
"""

import argparse
import statistics
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # `uv run scripts/...` puts scripts/, not the repo root, on the path

from api import config, ehr_document  # noqa: E402


def percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100 * len(s)))]


def render_all(conn: psycopg.Connection) -> int:
    ids = [r[0] for r in conn.execute("SELECT id FROM ehr.patient ORDER BY id").fetchall()]
    with conn.transaction():
        for pid in ids:
            conn.execute(
                """INSERT INTO ehr.record_document (patient_id, markdown) VALUES (%s, %s)
                   ON CONFLICT (patient_id) DO UPDATE SET markdown = EXCLUDED.markdown, rendered_at = now()""",
                [pid, ehr_document.render_patient(conn, pid)])
    return len(ids)


def report(conn: psycopg.Connection) -> None:
    docs = conn.execute("SELECT markdown FROM ehr.record_document").fetchall()
    if not docs:
        print("no documents; run without --stats first")
        return
    chars = [len(m) for (m,) in docs]
    sections = [len(ehr_document.parse_tree(m)) for (m,) in docs]
    biggest: dict[str, list[int]] = {}
    for (m,) in docs:
        for s in ehr_document.parse_tree(m):
            biggest.setdefault(s.section_id, []).append(s.chars)
    print(f"{len(docs)} documents")
    print(f"  characters: min {min(chars)}, median {int(statistics.median(chars))}, "
          f"p90 {int(percentile(chars, 90))}, max {max(chars)}   (about {int(statistics.median(chars)) // 4} tokens at the median)")
    print(f"  sections per document: {min(sections)} to {max(sections)}")
    print("  median characters per section:")
    for sid, sizes in biggest.items():
        print(f"    {sid:<22} {int(statistics.median(sizes)):>6}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", action="store_true", help="only report on the stored documents")
    ap.add_argument("--database-url", default=config.DATABASE_URL)
    args = ap.parse_args()
    with psycopg.connect(args.database_url, autocommit=True) as conn:
        if not args.stats:
            print(f"rendered {render_all(conn)} documents")
        report(conn)


if __name__ == "__main__":
    main()
