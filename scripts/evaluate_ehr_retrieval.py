"""Measure the vectorless branch against the SQL answer: how well can the active conditions be read back
from a patient's record document?

    python scripts/evaluate_ehr_retrieval.py --per-stratum 20            # tree + dense, needs the chat model
    python scripts/evaluate_ehr_retrieval.py --retrieval-only            # dense retrieval alone, needs only the embedder

The answer key is the `ehr` tables (a condition is active when a row has no stop date): the documents are
rendered from them, so no hand labelling is needed. SQL is therefore not a competitor here, it is the
reference, and it is what /recommend uses. Nothing below feeds a Filter.

Methods
  tree   LLM reads a table of contents, picks sections, lists active conditions from them.
  dense  fixed-size pieces, embedded; the k closest to the question go to the LLM, which lists the conditions.

Per patient, with T = true active codes, S = codes that appear in the document only as resolved, P = predicted:
  recall = |P&T| / |T|, precision = |P&T| / |P|, leak = |P&S| (a resolved condition reported as active).
Documents are split into three strata by length, so a method that only works on short records shows up.

Output goes to eval/ehr_runs/<timestamp>/ (config.json, patients.jsonl, summary.md), apart from the recipe eval.
"""

import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # `uv run scripts/...` puts scripts/, not the repo root, on the path

from api import config, ehr_document, ehr_navigator, embed, llm  # noqa: E402

STRATA = ("short", "medium", "long")


# ---------------------------------------------------------------------------
# Scoring (pure, tested)
# ---------------------------------------------------------------------------


def score(predicted: set[str], truth: set[str], stale: set[str]) -> dict:
    tp = len(predicted & truth)
    return {"truth_n": len(truth), "stale_n": len(stale), "predicted_n": len(predicted), "tp": tp,
            "leak": len(predicted & stale), "exact": predicted == truth}


def strata_by_length(lengths: dict[str, int]) -> dict[str, str]:
    """Patient id -> short | medium | long, by terciles of document length."""
    order = sorted(lengths, key=lambda k: (lengths[k], k))
    n = len(order)
    return {pid: STRATA[min(2, i * 3 // n)] for i, pid in enumerate(order)}


def summarize(rows: list[dict]) -> dict:
    """One line of numbers for a group of per-patient rows."""
    def mean(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(statistics.fmean(vals), 1) if vals else None
    ok = [r for r in rows if not r.get("error")]
    truth = sum(r["truth_n"] for r in ok)
    predicted = sum(r["predicted_n"] for r in ok)
    tp = sum(r["tp"] for r in ok)
    return {
        "patients": len(rows), "errors": len(rows) - len(ok),
        "recall": round(tp / truth, 3) if truth else None,
        "precision": round(tp / predicted, 3) if predicted else None,
        "exact": round(sum(r["exact"] for r in ok) / len(ok), 3) if ok else None,
        "leak_patients": round(sum(r["leak"] > 0 for r in ok) / len(ok), 3) if ok else None,
        "leak_codes": sum(r["leak"] for r in ok),
        "invented_codes": sum(r.get("rejected_n", 0) for r in ok),
        "chars_read": mean("chars_read"), "share_of_doc": mean("share_of_doc"),
        "llm_calls": mean("llm_calls"), "ms": mean("ms"),
    }


def summarize_retrieval(rows: list[dict]) -> dict:
    """For --retrieval-only: what the closest pieces contain, before any LLM reads them."""
    truth = sum(r["truth_n"] for r in rows)
    stale = sum(r["stale_n"] for r in rows)
    return {
        "patients": len(rows),
        "active_seen": round(sum(r["tp"] for r in rows) / truth, 3) if truth else None,
        "stale_seen": round(sum(r["leak"] for r in rows) / stale, 3) if stale else None,
        "patients_with_all_active_seen": round(sum(r["exact"] for r in rows) / len(rows), 3),
        "chars_read": round(statistics.fmean(r["chars_read"] for r in rows), 1),
        "share_of_doc": round(statistics.fmean(r["share_of_doc"] for r in rows), 3),
    }


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def pick_patients(strata: dict[str, str], per_stratum: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    chosen = []
    for name in STRATA:
        pool = sorted(pid for pid, s in strata.items() if s == name)
        chosen += rng.sample(pool, min(per_stratum, len(pool)))
    return chosen


def evaluate_patient(conn, http, pid: str, markdown: str, stratum: str, methods: list[str], args) -> list[dict]:
    rec = ehr_document.fetch_record(conn, pid)
    truth = ehr_document.active_condition_codes(rec)
    stale = ehr_document.resolved_only_condition_codes(rec)
    ask = lambda messages: llm.chat(http, messages, json_mode=True, model=args.model, timeout=args.timeout)  # noqa: E731
    docs = lambda texts: embed.embed_documents(http, texts)  # noqa: E731
    query = lambda text: embed.embed_query_array(http, text)  # noqa: E731
    rows = []
    for method in methods:
        t = time.perf_counter()
        if method == "tree":
            r = ehr_navigator.tree_active_conditions(markdown, ask)
        else:
            r = ehr_navigator.dense_active_conditions(markdown, ask, docs, query, k=args.k, max_chars=args.piece_chars)
        row = {"patient_id": pid, "stratum": stratum, "method": method, "doc_chars": len(markdown),
               **score(r.codes, truth, stale), "error": r.error, "rejected_n": len(r.rejected),
               "chars_read": r.chars_read, "share_of_doc": round(r.chars_read / len(markdown), 3),
               "llm_calls": r.llm_calls, "ms": round((time.perf_counter() - t) * 1000, 1),
               "selected": r.selected, "predicted": sorted(r.codes), "truth": sorted(truth)}
        rows.append(row)
    return rows


def retrieval_only(conn, http, pid: str, markdown: str, stratum: str, args) -> dict:
    rec = ehr_document.fetch_record(conn, pid)
    truth = ehr_document.active_condition_codes(rec)
    stale = ehr_document.resolved_only_condition_codes(rec)
    chosen = ehr_navigator.closest_pieces(markdown, lambda t: embed.embed_documents(http, t),
                                          lambda t: embed.embed_query_array(http, t), k=args.k, max_chars=args.piece_chars)
    text = "\n\n".join(p for _, p in chosen)
    seen_active = {c for c in truth if ehr_navigator.appears_in(c, text)}
    seen_stale = {c for c in stale if ehr_navigator.appears_in(c, text)}
    return {"patient_id": pid, "stratum": stratum, "method": "dense-retrieval", "doc_chars": len(markdown),
            "truth_n": len(truth), "stale_n": len(stale), "tp": len(seen_active), "leak": len(seen_stale),
            "exact": seen_active == truth, "chars_read": len(text), "share_of_doc": round(len(text) / len(markdown), 3),
            "selected": [str(n) for n, _ in chosen]}


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join("n/a" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def write_summary(path: Path, rows: list[dict], cfg: dict, lengths: dict[str, int]) -> str:
    docs = sorted(lengths.values())
    parts = [f"# EHR retrieval evaluation, {cfg['started']}", "",
             f"Answer key: the `ehr` tables. {len({r['patient_id'] for r in rows})} patients, "
             f"{cfg['per_stratum']} per length stratum, seed {cfg['seed']}. "
             f"Model `{cfg['model']}`, dense k={cfg['k']} pieces of up to {cfg['piece_chars']} characters.", "",
             f"Document length over all {len(docs)} patients: median {docs[len(docs) // 2]} characters "
             f"(about {docs[len(docs) // 2] // 4} tokens), 90th percentile {docs[int(len(docs) * .9)]}, max {docs[-1]}.", ""]
    methods = list(dict.fromkeys(r["method"] for r in rows))
    for method in methods:
        mrows = [r for r in rows if r["method"] == method]
        parts += [f"## {method}", ""]
        groups = [(s, [r for r in mrows if r["stratum"] == s]) for s in STRATA] + [("all", mrows)]
        if cfg["retrieval_only"]:
            headers = ["stratum", "patients", "active seen", "stale seen", "all active seen", "chars read", "share of doc"]
            body = []
            for s, g in groups:
                if g:
                    x = summarize_retrieval(g)
                    body.append([s, x["patients"], x["active_seen"], x["stale_seen"],
                                 x["patients_with_all_active_seen"], x["chars_read"], x["share_of_doc"]])
            parts += [table(headers, body), ""]
            continue
        headers = ["stratum", "patients", "errors", "recall", "precision", "exact", "patients with a stale leak",
                   "stale codes reported", "invented codes", "chars read", "share of doc", "LLM calls", "ms"]
        body = []
        for s, g in groups:
            if g:
                x = summarize(g)
                body.append([s, x["patients"], x["errors"], x["recall"], x["precision"], x["exact"], x["leak_patients"],
                             x["leak_codes"], x["invented_codes"], x["chars_read"], x["share_of_doc"], x["llm_calls"], x["ms"]])
        parts += [table(headers, body), ""]
    text = "\n".join(parts)
    path.write_text(text)
    return text


def preflight(http: httpx.Client, args) -> None:
    """Fail before the run, not after a hundred identical errors."""
    try:
        embed.embed_query_array(http, "ping")
    except httpx.HTTPError as e:
        raise SystemExit(f"The embedding service is not reachable ({e}). Start Ollama.")
    if not args.retrieval_only:
        try:
            llm.chat(http, [{"role": "user", "content": 'Reply with {"ok": true}'}], json_mode=True,
                     model=args.model, timeout=args.timeout, attempts=1)
        except llm.LLMError as e:
            raise SystemExit(f"The chat model is not usable: {e}\n"
                             f"If it is missing: ollama pull {args.model}   (or pass --model with one you have).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-stratum", type=int, default=20, help="patients per length stratum (default 20)")
    ap.add_argument("--seed", type=int, default=603)
    ap.add_argument("--methods", default="tree,dense", help="comma list of tree, dense")
    ap.add_argument("--retrieval-only", action="store_true", help="dense retrieval without the LLM (needs only the embedder)")
    ap.add_argument("--k", type=int, default=4, help="dense: pieces sent to the LLM")
    ap.add_argument("--piece-chars", type=int, default=800, help="dense: piece size in characters")
    ap.add_argument("--model", default=config.LLM_MODEL)
    ap.add_argument("--timeout", type=float, default=config.LLM_TIMEOUT)
    ap.add_argument("--out", default=str(ROOT / "eval" / "ehr_runs"))
    ap.add_argument("--database-url", default=config.DATABASE_URL)
    args = ap.parse_args()
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    if not set(methods) <= {"tree", "dense"}:
        raise SystemExit("--methods takes tree and/or dense")

    with psycopg.connect(args.database_url, autocommit=True) as conn, httpx.Client(timeout=args.timeout) as http:
        docs = {str(pid): md for pid, md in conn.execute("SELECT patient_id, markdown FROM ehr.record_document").fetchall()}
        if not docs:
            raise SystemExit("No documents. Run scripts/render_ehr_documents.py first.")
        lengths = {pid: len(md) for pid, md in docs.items()}
        strata = strata_by_length(lengths)
        chosen = pick_patients(strata, args.per_stratum, args.seed)
        preflight(http, args)

        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_dir = Path(args.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir.mkdir(parents=True)
        cfg = {"started": started, "per_stratum": args.per_stratum, "seed": args.seed, "model": args.model,
               "k": args.k, "piece_chars": args.piece_chars, "methods": methods, "retrieval_only": args.retrieval_only,
               "embed_model": config.EMBED_MODEL, "patients": len(chosen)}
        (run_dir / "config.json").write_text(json.dumps(cfg, indent=2))

        rows: list[dict] = []
        with (run_dir / "patients.jsonl").open("w") as f:
            for i, pid in enumerate(chosen, 1):
                if args.retrieval_only:
                    new = [retrieval_only(conn, http, pid, docs[pid], strata[pid], args)]
                else:
                    new = evaluate_patient(conn, http, pid, docs[pid], strata[pid], methods, args)
                for row in new:
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                rows += new
                print(f"[{i}/{len(chosen)}] {pid} {strata[pid]} " +
                      " ".join(f"{r['method']}:{r['tp']}/{r['truth_n']}" + ("!" if r.get("error") else "") for r in new), flush=True)
        print()
        print(write_summary(run_dir / "summary.md", rows, cfg, lengths))
        print(f"written to {run_dir}")


if __name__ == "__main__":
    main()
