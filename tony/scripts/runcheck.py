"""Rank check: a Timing repeat or Ablation run must rank every query exactly as the Report run did.

    uv run scripts/runcheck.py eval/runs/20260928-122309 eval/runs/<run> [eval/runs/<run> ...]

Compares the known Recipe's rank per (config, strategy, query id), on the run's `default` rows and only for
the configs the run holds. No tolerance: retrieval is deterministic, so any difference is a finding (a tie or
near-tie that flipped), not noise to allow. Exits 1 on any mismatch. The report bundle imports the same check.
"""

import csv
import json
import sys
from pathlib import Path

Key = tuple[str, str, str]  # (config, strategy, query id)


def default_ranks(run_dir: Path) -> dict[Key, str]:
    """Rank per key from per_query.csv ("" is a miss). Rows without a variant column are all default."""
    with open(run_dir / "per_query.csv", newline="") as f:
        return {(r["config"], r["strategy"], r["query_id"]): r["rank"] for r in csv.DictReader(f)
                if r.get("variant", "default") == "default"}


def rank_mismatches(report_run: Path, run_dir: Path) -> list[str]:
    """One line per key where `run_dir` differs from the Report run, for the configs `run_dir` holds.

    A `--limit` run (settings.json has a limit) is checked on the queries it holds; a full run on all of them.
    """
    expected, actual = default_ranks(report_run), default_ranks(run_dir)
    configs = {c for c, _, _ in actual}
    settings = run_dir / "settings.json"
    if settings.exists() and json.loads(settings.read_text()).get("limit"):
        held = {q for _, _, q in actual}
        expected = {k: rank for k, rank in expected.items() if k[2] in held}
    shown = lambda rank: rank or "miss"  # noqa: E731
    out = [f"{'/'.join(k)}: report {shown(rank)}, this run {shown(actual[k]) if k in actual else 'absent'}"
           for k, rank in expected.items() if k[0] in configs and actual.get(k) != rank]
    out += [f"{'/'.join(k)}: not in the report run" for k in actual if k not in expected]
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    report, failed = Path(sys.argv[1]), False
    for run in map(Path, sys.argv[2:]):
        problems = rank_mismatches(report, run)
        print(f"{run}: {'ranks match' if not problems else f'{len(problems)} mismatches'}")
        for line in problems[:20]:
            print(f"  {line}")
        failed |= bool(problems)
    sys.exit(1 if failed else 0)
