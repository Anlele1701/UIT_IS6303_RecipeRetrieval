"""Fill the report's numbers from the files the pipeline wrote (CLAUDE.md rule 9: no number typed by hand).

    uv run scripts/report_numbers.py            # docs/report/src/*.md -> docs/report/build/*.md
    uv run scripts/report_numbers.py --check    # also fail when a placeholder cannot be filled

A placeholder is {{source:path|format}}. The path walks the JSON with dots; a key that holds a dot or a space
is written in brackets: {{m6:summary.[S|t2].cvr_adj.mean|pct}}. Sources are the files in SOURCES. Formats:
  pct    0.0267 -> 2,7%          pct0   0.9333 -> 93%          f1 / f2 / f3   decimal comma, 1-3 places
  sf3    +0,465 (signed)         int    32719 -> 32.719        p      p-value: < 0,001 or 0,072
  ci     [lo, hi] -> [0,76; 0,89] (2 places)   cipct  [lo, hi] as % (1 place)   kn  {"k":14,"n":15} -> 14/15
  raw    as written
Source "d" holds counts derived here (derived()): checker errors, Thy's faithfulness labels.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "report" / "src"
BUILD = ROOT / "docs" / "report" / "build"
SOURCES = {
    "m6": ROOT / "eval" / "runs" / "20261019-093605" / "a3" / "metrics.json",
    "m6s": ROOT / "eval" / "runs" / "20261019-093605" / "a3" / "settings.json",
    "mv4": ROOT / "eval" / "runs" / "20261018-132948" / "patient" / "metrics.json",
    "corpus": ROOT / "eval" / "corpus.json",
    "pcorpus": ROOT / "eval" / "patient_corpus.json",
    "flow": ROOT / "eval" / "testset" / "testset_flow.json",
    "pq": ROOT / "eval" / "patient" / "queries_summary.json",
    "allergen": ROOT / "eval" / "labels" / "report_allergen.json",
    "a1": ROOT / "eval" / "m0_reproduction.json",
}
PLACEHOLDER = re.compile(r"\{\{(\w+):((?:\[[^\]]*\]|[^|}\[])+)(?:\|(\w+))?\}\}")  # [a|b] may hold a pipe
TOKEN = re.compile(r"\[([^\]]+)\]|([^.\[]+)")


def comma(x: float, places: int) -> str:
    return f"{x:.{places}f}".replace(".", ",").replace("-", "−")


def fmt(v, kind: str | None) -> str:
    kind = kind or "raw"
    if kind == "pct":
        return comma(100 * v, 1) + "%"
    if kind == "pct0":
        return f"{100 * v:.0f}%"
    if kind in {"f1", "f2", "f3"}:
        return comma(v, int(kind[1]))
    if kind == "sf3":
        return ("+" if v >= 0 else "−") + comma(abs(v), 3)
    if kind == "int":
        return f"{round(v):,}".replace(",", ".")
    if kind == "p":
        return "< 0,001" if v < 0.001 else comma(v, 3)
    if kind == "ci":
        return f"[{comma(v[0], 2)}; {comma(v[1], 2)}]"
    if kind == "cipct":
        return f"[{comma(100 * v[0], 1)}; {comma(100 * v[1], 1)}]"
    if kind == "kn":
        return f"{v['k']}/{v['n']}"
    if kind == "raw":
        return str(v)
    raise ValueError(f"unknown format {kind!r}")


def lookup(data: dict, path: str):
    cur = data
    for bracket, plain in TOKEN.findall(path):
        key = bracket or plain
        if isinstance(cur, list):
            cur = cur[int(key)]
        else:
            cur = cur[key]
    return cur


def render(text: str, data: dict[str, dict]) -> tuple[str, list[str]]:
    missing: list[str] = []

    def one(m: re.Match) -> str:
        src, path, kind = m.group(1), m.group(2), m.group(3)
        try:
            return fmt(lookup(data[src], path), kind)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            missing.append(f"{m.group(0)}: {type(e).__name__} {e}")
            return f"**[THIẾU {m.group(0)[2:-2]}]**"
    out = PLACEHOLDER.sub(one, text)
    missing += [f"not a placeholder: {m}" for m in re.findall(r"\{\{[^}]*\}\}", out)]  # malformed: never left silently
    return out, missing


def prompt_texts() -> dict[str, str]:
    """The prompts as the code holds them (appendix), fenced so Markdown keeps them verbatim."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_cards
    fence = "```"
    return {name: f"{fence}text\n{text.strip()}\n{fence}" for _, name, text in make_cards.prompts()}


def m1_schema() -> str:
    """The JSON schema M1 sends to Ollama (structured output), as code holds it."""
    sys.path.insert(0, str(ROOT))
    from api.pipeline.m1_understand import SCHEMA_PATIENT
    rows = ["| Trường | Kiểu | Giá trị cho phép |", "|---|---|---|"]
    for name, spec in SCHEMA_PATIENT["properties"].items():
        kind = spec.get("type", "")
        kind = " hoặc ".join(kind) if isinstance(kind, list) else kind
        items = spec.get("items", {})
        allowed = spec.get("enum") or items.get("enum") or []
        if kind == "array":
            kind = f"mảng {items.get('type', '')}".strip()
        rows.append(f"| `{name}` | {kind} | {', '.join(str(a) for a in allowed if a is not None) or '–'} |")
    return "\n".join(rows)


def derived() -> dict:
    """Counts no metrics file holds as one number, computed here from the run and label files."""
    import csv
    run = SOURCES["m6"].parent
    verdicts = json.loads((run / "checker_verdicts.json").read_text(encoding="utf-8"))
    with open(ROOT / "eval" / "labels" / "human_check.csv", encoding="utf-8", newline="") as f:
        rows = {r["item_id"]: json.loads(r["label"]) for r in csv.DictReader(f)}  # last row per item wins
    answers = [v for k, v in rows.items() if k.startswith("ans_")]
    return {"checker_errors": sum(v["contains"] == "error" for v in verdicts), "checker_verdicts": len(verdicts),
            "human_faithful": {"k": sum(bool(v["faithful"]) for v in answers), "n": len(answers),
                               "value": sum(bool(v["faithful"]) for v in answers) / len(answers)},
            "human_wrong_citation": {"k": sum(bool(v["wrong_citation"]) for v in answers), "n": len(answers)},
            "human_items": len(rows),
            "sample": {k: len(v) for k, v in json.loads(SOURCES["m6s"].read_text(encoding="utf-8"))["qids"].items()},
            "prompts": prompt_texts(),
            "m1_schema": m1_schema(),
            "turns": sum(1 for line in (run / "turns.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}


def main(check: bool) -> int:
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in SOURCES.items() if p.exists()}
    data["d"] = derived()
    BUILD.mkdir(parents=True, exist_ok=True)
    problems = []
    for src in sorted(SRC.glob("*.md")):
        out, missing = render(src.read_text(encoding="utf-8"), data)
        (BUILD / src.name).write_text(out, encoding="utf-8")
        problems += [f"{src.name}: {m}" for m in missing]
    print(f"{len(list(SRC.glob('*.md')))} files -> {BUILD.relative_to(ROOT)}; unfilled: {len(problems)}")
    for p in problems:
        print("  " + p)
    return 1 if check and problems else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
