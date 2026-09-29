# How ablation runs and timing repeats are stored

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

The Report page's manifest ("Page data contract") must name every run the page reads. Besides the report run there are now:

- 7 ablation arms × 3 Chunking strategies ("Which ablations to run") plus the exact-Dense arm ("What to do about approximate Dense search"), each timed against the default in the same run ("Latency vs accuracy framing");
- 3 timing repeats of the report run, whose latency is the median across them ("Latency vs accuracy framing").

Decide:

- One run folder per ablation arm, or one combined run? How is an arm's settings diff against the report run recorded?
- Where the timing repeats live (full run folders, or latency-only files beside the report run), and how the bundle script picks the median and range.
- Does `significance.json` for an arm live in the arm's folder or the report run's?
- What the manifest looks like for all of this.

## Answer

- **Ablation runs**: one run folder per arm. Each holds the arm and its default, interleaved per query, on all 3 Chunking strategies. A crash or re-run touches one arm only, and each folder stays a normal Evaluation run for `failures.py`, `significance.py` and the bundle.
- **Arm definition**: named arms in an `ARMS` dict in `scripts/evaluate.py`, run with `--arm <key>`, e.g. `"rrf-k-10": {"configs": ["fusion"], "set": {"rrf_k": 10}}`. No free-form overrides. `settings.json` gains an `arm` block (key, configs, overrides), so what an arm is gets written once, by the run that used it.
- **Arm rows**: a `variant` column (`default` / `arm`) in `per_query.csv` and `metrics.json`. `config` stays one of the 4 glossary names. This covers the exact-Dense arm, which touches Dense, the Fusion baseline and Hybrid.
- **Timing repeats**: 3 full run folders (all configs, all strategies) on the commit that has the config-order rotation, not `466b46a`. Accuracy comes from the Report run. The Report run's own latency is dropped because it was measured with the fixed order. Per config × strategy × stage: point = median of the 3 p50s, whisker = median of the 3 p95s, range = min–max of the 3 p50s. Pooling per-query timings was rejected because it hides the run-to-run drift the range is there to show.
- **Rank checks**: every Timing repeat's ranks, and every Ablation run's default ranks, must equal the Report run's. On any mismatch the bundle script fails hard; no tolerance. If MPS float noise ever flips a near-tie, that's a §3 finding. §3 states "latency from 3 Timing repeats on commit X, ranks verified identical".
- **Significance**: each folder's `significance.json` holds raw p only (for an Ablation run: arm vs its in-run default, paired). The bundle script applies Holm across every test in the runs the manifest names. Adding an arm can't leave stale adjusted p in old folders.
- **Manifest** `eval/report.json`, paths only:

```json
{
  "report_run": "eval/runs/20260928-122309",
  "timing_repeats": ["eval/runs/<ts>", "eval/runs/<ts>", "eval/runs/<ts>"],
  "ablation_runs": {
    "reranker-minilm-l6": "…", "reranker-mxbai-base": "…", "reranker-bge-v2-m3": "…",
    "rrf-k-10": "…", "rrf-k-100": "…", "rerank-top-20": "…", "rerank-top-100": "…", "exact-dense": "…"
  },
  "labels": { "query_edits": "eval/query_edits.csv", "error_groups": "eval/error_groups.csv" }
}
```

Folder names stay timestamps; the manifest gives them meaning.

- **Glossary**: added **Ablation run** and **Timing repeat** to `CONTEXT.md`.

Amends [Significance tests](06-significance-tests.md) (Holm moves to the bundle) and [Latency vs accuracy framing](09-latency-vs-accuracy.md) (repeats run on the later commit).

Build items for the spec: `ARMS` + `--arm` in `evaluate.py`; the `variant` column; the `arm` block in `settings.json`; config-order rotation; `significance.py` writes raw p and compares variants within a run; Holm and the rank checks in the bundle script; `eval/report.json`.
