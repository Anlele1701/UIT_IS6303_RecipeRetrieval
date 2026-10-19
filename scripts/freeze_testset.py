"""M5: apply Thy's V6 review and freeze the A3 test set (build plan M5; CLAUDE.md rule 8).

    uv run scripts/freeze_testset.py --approved-by Thy

Reads eval/testset/candidates/*.jsonl and eval/labels/testset_review.csv (the last row per item wins):
ok keeps the proposed gold, edit replaces it, drop removes the item. Refuses while an item is unreviewed.
Writes eval/testset/{t1,t2,t3,t4}.jsonl, adds the V6 counts to testset_flow.json and writes
eval/testset/frozen.json with their sha256. From then on make_testset.py refuses to run and
tests/test_make_testset.py fails if a frozen file changes. Unfreezing means deleting frozen.json (ask Thy first).
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import testset_review as tr  # noqa: E402

OUT = ROOT / "eval" / "testset"
FILES = [f"{s}.jsonl" for s in tr.SETS]


def digests() -> dict[str, str]:
    return {f: hashlib.sha256((OUT / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for f in FILES}


def apply(items: list[dict], reviews: dict[str, dict]) -> tuple[dict[str, list[dict]], dict]:
    """The frozen sets and the V6 counts. Raises ValueError listing unreviewed items."""
    missing = [it["id"] for it in items if it["id"] not in reviews]
    if missing:
        raise ValueError(f"{len(missing)} items not reviewed yet, e.g. {', '.join(missing[:5])}")
    not_thy = [i for i, r in reviews.items() if r.get("reviewer", "Thy") != "Thy"]
    if not_thy:
        raise ValueError(f"{len(not_thy)} review rows are not Thy's, e.g. {', '.join(not_thy[:5])}")
    sets: dict[str, list[dict]] = {s: [] for s in tr.SETS}
    counts = {s: {"ok": 0, "edit": 0, "drop": 0, "bulk_ok": 0} for s in tr.SETS}
    for it in items:
        r = reviews[it["id"]]
        counts[it["set"]][r["decision"]] += 1
        counts[it["set"]]["bulk_ok"] += r["note"] == tr.BULK_NOTE
        if r["decision"] == "drop":
            continue
        out = {k: v for k, v in it.items() if k not in {"needs_gold", "v3_warning", "must"}}
        if r["gold"]:  # an edit, or an accepted draft
            gold = json.loads(r["gold"])
            if "turns" in out:
                out["turns"] = [{**t, "gold": g} for t, g in zip(out["turns"], gold)]
            else:
                out["gold"] = gold
        out["review"] = {"decision": r["decision"], "note": r["note"]}
        sets[it["set"]].append(out)
    return sets, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--approved-by", required=True)
    args = ap.parse_args()
    frozen = OUT / "frozen.json"
    if frozen.exists():
        sys.exit("already frozen")
    try:
        sets, counts = apply(tr.items(), tr.saved())
    except ValueError as e:
        sys.exit(str(e))
    for s, rows in sets.items():
        (OUT / f"{s}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    flow_path = OUT / "testset_flow.json"
    flow = json.loads(flow_path.read_text(encoding="utf-8"))
    for s in tr.SETS:
        flow["sets"].setdefault(s, {})["V6"] = {"reviewed": sum(counts[s].values()), **counts[s],
                                                "final": len(sets[s])}
    flow["frozen_at"] = datetime.now().isoformat(timespec="seconds")
    flow_path.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    frozen.write_text(json.dumps({"frozen_at": flow["frozen_at"], "approved_by": args.approved_by,
                                  "sha256": digests()}, indent=2) + "\n", encoding="utf-8")
    print({s: len(r) for s, r in sets.items()}, digests())


if __name__ == "__main__":
    main()
