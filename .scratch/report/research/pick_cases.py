"""Shortlists for the 5 case buckets and context for the every-config misses (report run)."""
import csv, json, sys
from pathlib import Path
csv.field_size_limit(sys.maxsize)
RUN = Path("eval/runs/20260928-122309")
S = ["fixed", "semantic", "sentence"]; MISS = 21
# recipe_id = position after URL dedupe, 1-based
titles, seen = {}, set()
with open("data/recipe.csv", newline="") as f:
    for r in csv.DictReader(f):
        if r["url"] in seen: continue
        seen.add(r["url"]); titles[len(seen)] = (r["title"], r["category"])
Q = {q["query_id"]: q for q in map(json.loads, open("eval/queries.jsonl"))}
assert all(titles[q["recipe_id"]][0] == q["recipe_title"] for q in Q.values()), "title map broken"
R, TOP = {}, {}
for r in csv.DictReader(open(RUN / "per_query.csv")):
    k = (r["config"], r["strategy"], r["query_id"])
    R[k] = int(r["rank"]) if r["rank"] else MISS; TOP[k] = [int(x) for x in r["top_recipe_ids"].split()]
rk = lambda c, s, q: R[(c, s, q)]
rules = {
  "dense_win": lambda s, q: rk("dense", s, q) <= 10 < rk("sparse", s, q),
  "sparse_win": lambda s, q: rk("sparse", s, q) <= 10 < rk("dense", s, q),
  "rerank_hurt": lambda s, q: rk("hybrid", s, q) > rk("fusion", s, q),
  "rerank_help": lambda s, q: rk("hybrid", s, q) <= 5 and rk("hybrid", s, q) < rk("fusion", s, q),
  "miss": lambda s, q: all(rk(c, s, q) == MISS for c in ["sparse", "dense", "fusion", "hybrid"]),
}
fmt = lambda r: "-" if r == MISS else str(r)
out = {}
for name, rule in rules.items():
    ids = [q for q in sorted(Q) if all(rule(s, q) for s in S)]
    out[name] = ids
    print(f"\n## {name} ({len(ids)})")
    for q in ids:
        ranks = " | ".join(f"{s[:3]} " + "/".join(fmt(rk(c, s, q)) for c in ["sparse", "dense", "fusion", "hybrid"]) for s in S)
        top = TOP[("hybrid", "semantic", q)][:3]
        print(f"{q} ov={Q[q]['word_overlap']} \"{Q[q]['text']}\" -> {Q[q]['recipe_title']} [{titles[Q[q]['recipe_id']][1]}] | {ranks} | hyb-sem top3: " + "; ".join(titles[t][0] for t in top))
json.dump(out, open(".scratch/report/research/pick_cases_shortlists.json", "w"), indent=1)
