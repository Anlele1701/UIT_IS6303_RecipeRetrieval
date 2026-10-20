"""MV4b: the patient question set, its answer key and the manual-check sheet (spec 7.1-7.2).

    uv run scripts/make_patient_queries.py          # -> eval/patient/{queries,gold}.jsonl, manual_check.csv, summary
    uv run scripts/make_patient_queries.py --no-llm # templates only (tests, a machine without Ollama)

For every patient of eval/patient/sample.json, three questions, one per type:
  1 no_constraint    "gợi ý món tối nhanh cho bệnh nhân này": the record's constraints must apply by themselves
  2 added_constraint a diet, a time limit or an excluded ingredient on top of the record
  3 needs_context    the latest labs or the latest visit: V2 must pick the right context node
Language: Vietnamese or English, seeded. No question is written by a person (Thy, MV4): each comes from a template
and is paraphrased by llama3.1:8b (another family than the qwen2.5 of M1; seed 42, cached) in a seeded "voice"
(nurse, caregiver, dietitian...) so one template gives several wordings. A paraphrase that drops a number, an
ingredient, the diet word, the patient or the language, or that ADDS a diet, ingredient, allergen, time, number or
list, is not used: the template stays (recorded as paraphrase_ok = false).
V7: a type 1/2 question must leave at least one Recipe that keeps the record's hard constraints and the question's
(counted on chunk_semantic with M4's own conditions); otherwise the next variant is tried, and a question no variant
can satisfy is kept and marked unanswerable. The answer key (gold.jsonl) comes from the coded entries (P2-P7), at
entity level: food-allergy substances, disorders and medications in force. Refuses to run once the set is frozen.
"""

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from api import config  # noqa: E402
from api.patient import profile_store, rules  # noqa: E402
from api.pipeline import m4_retrieve as m4  # noqa: E402
from api.pipeline.llm import LLMError, chat_json  # noqa: E402
from api.pipeline.schemas import Constraints  # noqa: E402
from api.textmatch import looks_vietnamese  # noqa: E402

SEED = 42
PARAPHRASE_MODEL = "llama3.1:8b"
OUT = ROOT / "eval" / "patient"
FROZEN = OUT / "frozen.json"
MANUAL_N = 20

DISHES = [("bữa tối nhanh", "quick dinner"), ("món súp", "soup"), ("bữa sáng", "breakfast"), ("món gà", "chicken dish"),
          ("món tráng miệng", "dessert"), ("món mì", "pasta dish"), ("món salad", "salad")]
INGREDIENTS = [("ngò", "cilantro", "cilantro"), ("nấm", "mushrooms", "mushroom"), ("hành tây", "onions", "onion"),
               ("cà chua", "tomatoes", "tomato"), ("tỏi", "garlic", "garlic")]
TYPE1 = {"vi": "gợi ý {dish} cho bệnh nhân này", "en": "suggest a {dish} for this patient"}
TYPE2 = [  # (key, vi, en, constraints)
    ("diet", "gợi ý {dish} chay cho bệnh nhân này", "suggest a vegetarian {dish} for this patient",
     lambda ing: {"diet": "vegetarian"}),
    ("time", "gợi ý {dish} nấu dưới 30 phút cho bệnh nhân này", "suggest a {dish} ready in under 30 minutes for this patient",
     lambda ing: {"max_total_minutes": 30}),
    ("exclude", "gợi ý {dish} không có {ing_vi} cho bệnh nhân này", "suggest a {dish} without {ing_en} for this patient",
     lambda ing: {"ingredients_exclude": [ing[2]]}),
]
TYPE3 = [  # (key, vi, en, the node kind that answers it)
    ("labs", "lần xét nghiệm gần nhất của bệnh nhân có gì cần lưu ý khi ăn uống không?",
     "what did the patient's most recent lab tests show that matters for meals?", "results"),
    ("visit", "lần khám gần nhất của bệnh nhân là khám gì?", "what was the patient's most recent visit for?", "encounters"),
]
PATIENT_WORD = {"vi": re.compile(r"bệnh nhân|benh nhan", re.I), "en": re.compile(r"patient", re.I)}
SYSTEM = ("Rewrite the user's request as ONE short sentence, in the SAME language, in this voice: {voice}. Keep its "
          "meaning exactly. Keep every number, every food or ingredient word, the word vegetarian/chay if present, and "
          "the reference to the patient. Add NOTHING: no diet, no ingredient, no time, no recipe, no list. "
          "Answer with JSON only.")
VOICES = ["a nurse typing quickly", "a caregiver asking politely", "a dietitian writing a short note",
          "a family member asking casually", "a doctor writing tersely", "a hospital kitchen assistant"]
SCHEMA = {"type": "object", "required": ["paraphrase"], "properties": {"paraphrase": {"type": "string"}}}
# words a paraphrase may not ADD (Thy's rule: the dialogue constraints are the template's, nothing else)
CONSTRAINT_WORDS = re.compile(
    r"vegetarian|vegan|plant-based|chay|thuần chay|minute|phút|gluten|dairy|lactose|low[- ]|ít |không có|without|"
    r"free|allerg|dị ứng|nut|hạt|đậu phộng|peanut|shellfish|tôm|hải sản|seafood|fish|cá |egg|trứng|milk|sữa|soy|"
    r"đậu nành|sesame|mè|wheat|lúa mì|" + "|".join(re.escape(w) for i in INGREDIENTS for w in i[:2]), re.I)


FOOD_WORDS: set[str] = set()  # filled from the ingredient lexicon by load_food_words()


def load_food_words(conn) -> None:
    """Single words of the canonical ingredient names and the Vietnamese aliases (4+ letters): a paraphrase may not
    bring in a food the template does not name (pq019: "... salad with roasted vegetables and avocado")."""
    words = set()
    for (name,) in conn.execute("SELECT canonical_name FROM ingredient"):
        words |= {w for w in re.findall(r"[a-z]+", name.lower()) if len(w) >= 4}
    for (alias,) in conn.execute("SELECT DISTINCT alias FROM ingredient_alias_vi"):
        if len(alias) >= 3:
            words.add(alias.lower())
    FOOD_WORDS.clear()
    FOOD_WORDS.update(words - {"patient", "this", "with", "dish", "meal", "quick", "recipe", "suggest", "salad", "soup",
                               "chicken", "pasta", "dessert", "breakfast", "dinner"})


def added_food(text: str, template: str) -> set[str]:
    def found(t):
        low = t.lower()
        return {w for w in FOOD_WORDS if re.search(rf"(?<!\w){re.escape(w)}s?(?!\w)", low)}
    return found(text) - found(template)


def keeps(text: str, lang: str, must: list[str], template: str = "") -> bool:
    """The paraphrase still says what the template says, in its language, and adds no constraint, food, number or
    list."""
    low = text.lower()
    if not (PATIENT_WORD[lang].search(text) and looks_vietnamese(text) == (lang == "vi")
            and all(m.lower() in low for m in must)):
        return False
    if template:
        def words(t):  # "without", "-free" and "không có" say the same thing
            return {"NOT" if w.lower() in {"without", "free", "không có"} else w.lower() for w in CONSTRAINT_WORDS.findall(t)}
        added = words(text) - words(template)
        new_numbers = set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", template))
        if added or new_numbers or len(text) > 2 * len(template) + 30 or text.count(",") > template.count(",") + 1:
            return False
        if added_food(text, template):
            return False
    return True


def paraphrase(client, text: str, lang: str, must: list[str], voice: str = VOICES[0]) -> tuple[str, bool]:
    if client is None:
        return text, False
    system = SYSTEM.format(voice=voice)
    try:
        out = chat_json(client, SCHEMA, [{"role": "system", "content": system}, {"role": "user", "content": text}],
                        model=PARAPHRASE_MODEL, temperature=0.0)
    except (LLMError, httpx.HTTPError):
        return text, False
    p = str(out.get("paraphrase", "")).strip()
    return (p, True) if p and keeps(p, lang, must, text) else (text, False)


def satisfiable(conn, profile, extra: dict) -> int:
    """Recipes left by the record's hard constraints plus the question's (M4's own conditions, unknown kept)."""
    c = Constraints(allergens_exclude=sorted(profile.allergens_exclude),
                    ingredients_exclude=sorted(set(profile.ingredients_exclude) | set(extra.get("ingredients_exclude", []))),
                    diet=extra.get("diet"), max_total_minutes=extra.get("max_total_minutes"),
                    nutrient_limits=dict(profile.nutrient_limits))
    from psycopg import sql
    cond, params = m4.conditions(c, norm=True, unknown_strict=False)
    q = sql.SQL("SELECT count(DISTINCT recipe_id) FROM {t} AS x WHERE id @@@ pdb.all() AND {c}").format(
        t=sql.Identifier(f"chunk_{config.CHAT_STRATEGY}"), c=cond)
    return conn.execute(q, params).fetchone()[0]


def gold_of(pid: str, nodes) -> dict:
    facts = {n.node_id: n.facts for n in nodes}
    return {"patient_id": pid,
            "food_allergy_substances": sorted({a["substance_code"] for a in facts.get("allergies", [])
                                               if a.get("kind_code") == "414285001" and a.get("substance_code")}),
            "conditions": sorted({p["code"] for p in facts.get("problems.active", []) if p.get("code")}),
            "medications": sorted({m["code"] for m in facts.get("meds.active", []) if m.get("code")}),
            "latest_node": {kind: max((n.node_id for n in nodes if n.node_id.startswith(kind + ".")),
                                      key=lambda i: i.split(".")[1], default=None) for kind in ("results", "encounters")}}


def build(conn, client, sample: list[dict], rs) -> tuple[list[dict], list[dict], Counter]:
    rng = random.Random(SEED)
    voices = random.Random(SEED + 2)  # its own stream: the voice never shifts the dish, language or constraint draws
    queries, gold, log = [], [], Counter()
    for p in sample:
        pid = p["patient_id"]
        nodes = profile_store.load_nodes(conn, pid)
        profile = profile_store.load_or_build(conn, pid, rs)
        g = gold_of(pid, nodes)
        gold.append(g)
        dishes = rng.sample(DISHES, 2)
        variants2 = rng.sample(TYPE2, len(TYPE2))
        langs = [rng.choice(["vi", "en"]) for _ in range(3)]
        base = {"patient_id": pid, "source": p["source"], "primary": p["primary"], "strata": p["strata"]}

        # type 1: the record alone
        lang = langs[0]
        text = TYPE1[lang].format(dish=dishes[0][0 if lang == "vi" else 1])
        msg, ok = paraphrase(client, text, lang, [], voices.choice(VOICES))
        n = satisfiable(conn, profile, {})
        queries.append({**base, "type": "no_constraint", "lang": lang, "template": text, "message": msg,
                        "paraphrase_ok": ok, "dialogue_constraints": {}, "v7_recipes": n, "unanswerable": n == 0})
        log["type1_unanswerable"] += n == 0

        # type 2: one dialogue constraint on top; the next variant when V7 fails
        lang = langs[1]
        chosen = None
        for key, vi, en, cons in variants2:
            ing = rng.choice(INGREDIENTS)
            extra = cons(ing)
            n = satisfiable(conn, profile, extra)
            chosen = (key, vi, en, extra, ing, n)
            if n > 0:
                break
            log["type2_variant_retried"] += 1
        key, vi, en, extra, ing, n = chosen
        dish = dishes[1][0 if lang == "vi" else 1]
        text = (vi if lang == "vi" else en).format(dish=dish, ing_vi=ing[0], ing_en=ing[1])
        must = {"diet": ["chay" if lang == "vi" else "vegetarian"], "time": ["30"],
                "exclude": [ing[0] if lang == "vi" else ing[1].rstrip("s")]}[key]
        msg, ok = paraphrase(client, text, lang, must, voices.choice(VOICES))
        queries.append({**base, "type": "added_constraint", "variant": key, "lang": lang, "template": text,
                        "message": msg, "paraphrase_ok": ok, "dialogue_constraints": extra, "v7_recipes": n,
                        "unanswerable": n == 0})
        log["type2_unanswerable"] += n == 0

        # type 3: the latest labs or visit; the answering node is the newest of its kind
        lang = langs[2]
        key, vi, en, kind = TYPE3[rng.randrange(len(TYPE3))]
        if not g["latest_node"].get(kind):
            key, vi, en, kind = next(t for t in TYPE3 if g["latest_node"].get(t[3]))
        text = vi if lang == "vi" else en
        msg, ok = paraphrase(client, text, lang, [], voices.choice(VOICES))
        queries.append({**base, "type": "needs_context", "variant": key, "lang": lang, "template": text,
                        "message": msg, "paraphrase_ok": ok, "dialogue_constraints": {},
                        "relevant_nodes": [g["latest_node"][kind]]})
    for i, q in enumerate(queries, 1):
        q["qid"] = f"pq{i:03d}"
    return queries, gold, log


def manual_sheet(conn, sample: list[dict], n: int = MANUAL_N) -> list[list]:
    """n patients (seeded, every primary stratum first) for Thy to check the answer key against the raw file."""
    rng = random.Random(SEED + 1)
    by = {}
    for p in sample:
        by.setdefault(p["primary"], []).append(p)
    picked = []
    for s in sorted(by):
        picked.append(rng.choice(by[s]))
    rest = [p for p in sample if p not in picked]
    picked += rng.sample(rest, max(0, n - len(picked)))
    rows = []
    for p in sorted(picked, key=lambda x: x["patient_id"]):
        nodes = {nd.node_id: nd.facts for nd in profile_store.load_nodes(conn, p["patient_id"])}
        src = conn.execute("SELECT source_dir || '/' || source_file FROM patient WHERE patient_id = %s",
                           [p["patient_id"]]).fetchone()[0]
        rows.append([p["patient_id"], p["source"], src,
                     "; ".join(f"{a['substance']} ({a['substance_code']})" for a in nodes.get("allergies", [])
                               if a.get("kind_code") == "414285001"),
                     "; ".join(f"{x['display']} ({x['code']})" for x in nodes.get("problems.active", [])),
                     "; ".join(f"{x['display']} ({x['code']})" for x in nodes.get("meds.active", [])),
                     "", "", "", ""])
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    if FROZEN.exists():
        sys.exit(f"{FROZEN.relative_to(ROOT)} exists: the question set is frozen (rule 8); nothing is rewritten")
    sample = json.loads((OUT / "sample.json").read_text(encoding="utf-8"))["patients"]
    rs = rules.load_rules()
    client = None if args.no_llm else httpx.Client(timeout=600)
    with psycopg.connect(config.DATABASE_URL) as conn:
        load_food_words(conn)
        queries, gold, log = build(conn, client, sample, rs)
        sheet = manual_sheet(conn, sample)
    for name, rows in (("queries.jsonl", queries), ("gold.jsonl", gold)):
        (OUT / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    with open(OUT / "manual_check.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["patient_id", "source", "file", "food_allergies_key", "conditions_key", "medications_key",
                    "allergies_ok", "conditions_ok", "medications_ok", "note"])
        w.writerows(sheet)
    summary = {"ran_at": datetime.now().isoformat(timespec="seconds"), "seed": SEED,
               "paraphrase_model": None if args.no_llm else PARAPHRASE_MODEL, "patients": len(sample),
               "questions": len(queries), "by_type": dict(Counter(q["type"] for q in queries)),
               "by_lang": dict(Counter(q["lang"] for q in queries)),
               "by_type2_variant": dict(Counter(q.get("variant") for q in queries if q["type"] == "added_constraint")),
               "paraphrase_kept": sum(q["paraphrase_ok"] for q in queries),
               "unanswerable": sum(bool(q.get("unanswerable")) for q in queries), "log": dict(log),
               "v7_min_recipes": min(q["v7_recipes"] for q in queries if "v7_recipes" in q),
               "manual_check_patients": len(sheet), "written_by_people": 0}
    (OUT / "queries_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
