"""Freeze the patient question set once Thy has approved it (MV4b; like rule 8 for eval/testset).

    uv run scripts/freeze_patient_set.py --approved-by Thy

Writes eval/patient/frozen.json with the sha256 of queries.jsonl and gold.jsonl. From then on
scripts/make_patient_queries.py refuses to run and tests/patient/test_patient_queries.py fails if either file
changes. Unfreezing means deleting frozen.json, which needs Thy's go-ahead (CLAUDE.md rule 3).
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "eval" / "patient"
FILES = ["queries.jsonl", "gold.jsonl"]


def digests() -> dict[str, str]:
    return {f: hashlib.sha256((DIR / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for f in FILES}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--approved-by", required=True)
    args = ap.parse_args()
    out = DIR / "frozen.json"
    if out.exists():
        sys.exit("already frozen")
    out.write_text(json.dumps({"frozen_at": datetime.now().isoformat(timespec="seconds"), "approved_by": args.approved_by,
                               "sha256": digests()}, indent=2) + "\n", encoding="utf-8")
    print(f"frozen: {digests()}")


if __name__ == "__main__":
    main()
