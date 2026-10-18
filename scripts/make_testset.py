"""M5: candidates for the A3 test set (T1-T4), filtered by V1-V5, with gold intent and constraints.

    uv run scripts/make_testset.py                 # -> eval/testset/candidates/{t1,t2,t3,t4}.jsonl, testset_flow.json
    uv run scripts/make_testset.py --no-llm        # no paraphrase (templates as written), for a quick look

Sets (sườn báo cáo 4.1; build plan M5):
- T1 regression: A1 queries (eval/queries.jsonl), seeded sample. Gold: search, no constraint; a query whose words
  look like a constraint (vegetarian, gluten-free, without...) is flagged `needs_gold` for Thy to fill at V6.
- T2 one-turn constraints: bilingual templates (dish x constraint), paraphrased by llama3.1:8b (another family than
  M1's qwen2.5:7b), half Vietnamese. Gold comes from the template.
- T3 unanswerable: dish x constraint combinations SQL finds no Recipe for, plus out-of-scope questions.
- T4 multi-turn: 2-4 turn scripts, a constraint stated in an earlier turn; gold per turn.
- Handwritten (eval/testset/handwritten.csv, Thy): gold left empty, filled by Thy at V6 (never M1's guess).

Filters, each with its code and count in testset_flow.json:
  V1 no recipe title copied   V2 a Recipe fits, checked by the INDEPENDENT checker (T3: SQL finds none)
  V3 language                 V4 no near duplicate (token Jaccard >= 0.8)       V5 3-40 words
  V6 (Thy, scripts/testset_review.py) and the freeze (scripts/freeze_testset.py) come after.
V3 is its own check (Vietnamese = has Vietnamese diacritics), not M1's detect_lang: an M1 language slip must
show in the evaluation, not shrink the test set. Seed 42 everywhere; refuses to run once the set is frozen.
"""

import argparse
import csv
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SEED = 42
PARAPHRASE_MODEL = "llama3.1:8b"
OUT = ROOT / "eval" / "testset"
CAND = OUT / "candidates"
FROZEN = OUT / "frozen.json"
HANDWRITTEN = OUT / "handwritten.csv"
TARGET = {"t1": 100, "t2": 150, "t3": 50, "t4": 50}
V2_RECIPES = 5  # Recipes the checker reads per query before V2 gives up
JACCARD = 0.8

# dish: (vi, en, title keyword for SQL)
DISHES = [("món gà", "chicken dish", "chicken"), ("món súp", "soup", "soup"), ("món mì Ý", "pasta dish", "pasta"),
          ("món salad", "salad", "salad"), ("bánh quy", "cookies", "cookie"), ("món cà ri", "curry", "curry"),
          ("món xào", "stir-fry", "stir-fry"), ("bánh ngọt", "cake", "cake"), ("món bò", "beef dish", "beef"),
          ("món cơm", "rice dish", "rice"), ("bánh mì", "bread", "bread"), ("món tráng miệng", "dessert", "pie")]
ALLERGENS = {"milk": ("sữa", "milk"), "egg": ("trứng", "eggs"), "fish": ("cá", "fish"),
             "crustacean_shellfish": ("tôm cua", "shellfish"), "tree_nuts": ("các loại hạt như hạnh nhân", "tree nuts"),
             "peanut": ("đậu phộng", "peanuts"), "wheat": ("lúa mì", "wheat"), "soy": ("đậu nành", "soy"),
             "sesame": ("mè", "sesame")}
INGREDIENTS = [("ngò", "cilantro", "cilantro"), ("nấm", "mushrooms", "mushroom"), ("hành tây", "onions", "onion"),
               ("cà chua", "tomatoes", "tomato"), ("tỏi", "garlic", "garlic"), ("ớt chuông", "bell peppers", "bell pepper")]
DIETS = {"vegetarian": ("chay", "vegetarian"), "vegan": ("thuần chay", "vegan")}
MINUTES = [15, 30, 45]

T2_TEMPLATES = {  # kind -> (vi, en); {dish} {a} {ing} {diet} {n}
    "allergen": ("tôi dị ứng {a}, gợi ý giúp tôi {dish}", "I'm allergic to {a}, suggest a {dish}"),
    "exclude": ("gợi ý {dish} không có {ing}", "suggest a {dish} without {ing}"),
    "diet": ("gợi ý {dish} {diet}", "suggest a {diet} {dish}"),
    "time": ("gợi ý {dish} nấu dưới {n} phút", "suggest a {dish} ready in under {n} minutes"),
    "allergen+time": ("tôi dị ứng {a}, cần {dish} nấu dưới {n} phút", "I'm allergic to {a}, I need a {dish} in under {n} minutes"),
    "diet+exclude": ("gợi ý {dish} {diet} không có {ing}", "suggest a {diet} {dish} without {ing}"),
    "allergen+diet": ("tôi dị ứng {a}, gợi ý {dish} {diet}", "I'm allergic to {a}, suggest a {diet} {dish}"),
}
T3_CONFLICTS = [  # dish words that clash with a constraint: (vi dish, en dish, title keyword, constraint)
    ("món bò hầm", "beef stew", "beef stew", {"diet": "vegan"}), ("gà rán", "fried chicken", "fried chicken", {"diet": "vegetarian"}),
    ("cá hồi nướng", "baked salmon", "salmon", {"allergens_exclude": ["fish"]}),
    ("tôm chiên tỏi", "garlic shrimp", "shrimp", {"allergens_exclude": ["crustacean_shellfish"]}),
    ("trứng tráng", "omelet", "omelet", {"allergens_exclude": ["egg"]}),
    ("bánh quy bơ đậu phộng", "peanut butter cookies", "peanut butter cookie", {"allergens_exclude": ["peanut"]}),
    ("bánh phô mai", "cheesecake", "cheesecake", {"allergens_exclude": ["milk"]}),
    ("mì Ý sốt kem", "fettuccine alfredo", "alfredo", {"allergens_exclude": ["milk"]}),
    ("sườn heo nướng", "pork ribs", "ribs", {"diet": "vegetarian"}),
    ("bánh mì bơ tỏi", "garlic bread", "garlic bread", {"allergens_exclude": ["wheat"]}),
    ("pesto húng quế", "basil pesto", "pesto", {"allergens_exclude": ["tree_nuts"], "diet": "vegan"}),
    ("đậu phụ sốt", "tofu stir-fry", "tofu", {"allergens_exclude": ["soy"]}),
    ("gà nướng mè", "sesame chicken", "sesame chicken", {"allergens_exclude": ["sesame"]}),
    ("bò bít tết", "steak", "steak", {"diet": "vegan", "max_total_minutes": 15}),
    ("bánh kem dâu", "strawberry cake", "strawberry cake", {"allergens_exclude": ["wheat", "egg", "milk"]}),
]
T3_OUT_OF_SCOPE = [("dự báo thời tiết Hà Nội ngày mai", "what's the weather in Hanoi tomorrow"),
                   ("123 nhân 47 bằng bao nhiêu", "what is 123 times 47"),
                   ("tôi bị đau bụng, nên uống thuốc gì", "I have a stomach ache, which medicine should I take"),
                   ("viết giúp tôi một bài thơ về mùa thu", "write me a poem about autumn"),
                   ("tỉ giá đô la hôm nay là bao nhiêu", "what is the dollar exchange rate today"),
                   ("tôi có nên ngừng thuốc huyết áp không", "should I stop my blood pressure medication"),
                   ("đội nào vô địch World Cup 2022", "who won the 2022 World Cup"),
                   ("dịch câu này sang tiếng Nhật giúp tôi", "translate this sentence into Japanese")]
T4_SCRIPTS = [  # turns: (vi, en, intent, change to the state); ref = position asked about
    [("gợi ý {dish} cho bữa tối", "suggest a {dish} for dinner", "search", {}),
     ("không dùng {ing} nhé", "no {ing} please", "refine", {"ingredients_exclude": "+ing"}),
     ("món thứ 2 làm thế nào?", "how do I make the second one?", "ask_detail", {"ref_recipe": 2})],
    [("tôi dị ứng {a}, gợi ý {dish}", "I'm allergic to {a}, suggest a {dish}", "search", {"allergens_exclude": "+a"}),
     ("cần nấu dưới {n} phút", "it has to be ready in under {n} minutes", "refine", {"max_total_minutes": "n"}),
     ("món đầu tiên cần những nguyên liệu gì?", "what goes into the first one?", "ask_detail", {"ref_recipe": 1})],
    [("gợi ý {dish} {diet}", "suggest a {diet} {dish}", "search", {"diet": "diet"}),
     ("thêm điều kiện không có {ing}", "also without {ing}", "refine", {"ingredients_exclude": "+ing"}),
     ("thôi, không cần {diet} nữa", "never mind, it doesn't have to be {diet}", "refine", {"diet": None})],
    [("tôi dị ứng {a}, gợi ý {dish}", "I'm allergic to {a}, suggest a {dish}", "search", {"allergens_exclude": "+a"}),
     ("giờ tôi ăn được {a} rồi, gợi ý lại {dish}", "actually I can eat {a} now, suggest a {dish} again", "refine",
      {"allergens_exclude": "-a"})],
    [("gợi ý {dish}", "suggest a {dish}", "search", {}),
     ("tôi dị ứng {a}", "I'm allergic to {a}", "refine", {"allergens_exclude": "+a"}),
     ("cần nấu dưới {n} phút", "it has to be ready in under {n} minutes", "refine", {"max_total_minutes": "n"}),
     ("món thứ 3 làm thế nào?", "how do I make the third one?", "ask_detail", {"ref_recipe": 3})],
]
VOICES = ["someone typing quickly on a phone", "a polite home cook", "a busy parent", "a student asking casually",
          "someone writing a short note", "an older person asking carefully"]
SYSTEM = ("Rewrite the user's request as ONE short sentence, in the SAME language, in this voice: {voice}. Keep its "
          "meaning exactly. Keep every number, every food, dish or ingredient word, every allergy and every diet word. "
          "Add NOTHING: no diet, no allergy, no ingredient, no time, no recipe, no list. Answer with JSON only.")
SCHEMA = {"type": "object", "required": ["paraphrase"], "properties": {"paraphrase": {"type": "string"}}}
CONSTRAINT_WORDS = re.compile(
    r"vegetarian|vegan|plant-based|chay|thuần chay|minute|phút|gluten|dairy|lactose|low[- ]|ít |không có|without|"
    r"free|allerg|dị ứng|nut|hạt|đậu phộng|peanut|shellfish|tôm|cua|hải sản|seafood|fish|cá |egg|trứng|milk|sữa|soy|"
    r"đậu nành|sesame|mè|wheat|lúa mì", re.I)
T1_CONSTRAINT_HINT = re.compile(r"vegetarian|vegan|gluten|dairy|nut[- ]free|without|no-bake|low[- ]|minute|keto|paleo", re.I)
VI_MARKS = re.compile(r"[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]", re.I)


# ---- text helpers --------------------------------------------------------------------------------------------

def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c)).replace("đ", "d")


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", fold(s)))


def jaccard(a: str, b: str) -> float:
    x, y = tokens(a), tokens(b)
    return len(x & y) / len(x | y) if x | y else 1.0


def lang_ok(text: str, lang: str) -> bool:
    """V3: Vietnamese has Vietnamese diacritics; English has none (independent of M1's detector)."""
    return bool(VI_MARKS.search(text)) == (lang == "vi")


def words(text: str) -> int:
    return len(text.split())


def keeps(text: str, template: str, lang: str, must: list[str]) -> bool:
    """A paraphrase keeps the template's language, numbers and key words, and adds no constraint or food."""
    from make_patient_queries import added_food
    low = text.lower()
    if not lang_ok(text, lang) or not all(m.lower() in low for m in must):
        return False

    def cw(t):
        return {"NOT" if w.lower() in {"without", "free", "không có"} else w.lower() for w in CONSTRAINT_WORDS.findall(t)}
    if cw(text) - cw(template) or set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", template)):
        return False
    return len(text) <= 2 * len(template) + 30 and text.count(",") <= template.count(",") + 1 \
        and not added_food(text, template)


def paraphrase(client, text: str, lang: str, must: list[str], voice: str) -> tuple[str, bool]:
    if client is None:
        return text, False
    import httpx

    from api.pipeline.llm import LLMError, chat_json
    try:
        out = chat_json(client, SCHEMA, [{"role": "system", "content": SYSTEM.format(voice=voice)},
                                         {"role": "user", "content": text}], model=PARAPHRASE_MODEL, temperature=0.0)
    except (LLMError, httpx.HTTPError):
        return text, False
    p = str(out.get("paraphrase", "")).strip().strip('"')
    return (p, True) if p and keeps(p, text, lang, must) else (text, False)


# ---- gold and generation (pure; tested) ------------------------------------------------------------------------

def empty_constraints() -> dict:
    return {"allergens_exclude": [], "ingredients_exclude": [], "diet": None, "max_total_minutes": None}


def t2_items(rng: random.Random, n: int) -> list[dict]:
    """n template items, balanced over kinds and languages, gold from the template."""
    kinds = list(T2_TEMPLATES)
    out = []
    for i in range(n):
        kind, lang = kinds[i % len(kinds)], ("vi", "en")[(i // len(kinds)) % 2]
        dish = rng.choice(DISHES)
        a = rng.choice(list(ALLERGENS))
        ing = rng.choice(INGREDIENTS)
        diet = rng.choice(list(DIETS))
        n_min = rng.choice(MINUTES)
        li = 0 if lang == "vi" else 1
        template = T2_TEMPLATES[kind][li].format(dish=dish[li], a=ALLERGENS[a][li], ing=ing[li], diet=DIETS[diet][li], n=n_min)
        c = empty_constraints()
        must = [dish[li].split()[-1]]
        if "allergen" in kind:
            c["allergens_exclude"] = [a]
            must.append(ALLERGENS[a][li].split()[0])
        if "exclude" in kind:
            c["ingredients_exclude"] = [ing[2]]
            must.append(ing[li].split()[0])
        if "diet" in kind:
            c["diet"] = diet
            must.append(DIETS[diet][li])
        if "time" in kind:
            c["max_total_minutes"] = n_min
            must.append(str(n_min))
        out.append({"set": "t2", "lang": lang, "kind": kind, "template": template, "text": template, "must": must,
                    "dish_keyword": dish[2], "gold": {"intent": "search", "constraints": c}})
    return out


def t3_items() -> list[dict]:
    out = []
    for vi, en, kw, cons in T3_CONFLICTS:
        for lang, dish in (("vi", vi), ("en", en)):
            c = {**empty_constraints(), **cons}
            n = c["max_total_minutes"]
            if lang == "vi":
                bits = ([DIETS[c["diet"]][0]] if c["diet"] else []) \
                    + ([f"không có {', '.join(ALLERGENS[a][0] for a in c['allergens_exclude'])}"] if c["allergens_exclude"] else []) \
                    + ([f"nấu dưới {n} phút"] if n else [])
                text = f"công thức {dish} {' '.join(bits)}"
            else:
                bits = ([DIETS[c["diet"]][1]] if c["diet"] else []) + [f"{ALLERGENS[a][1]}-free" for a in c["allergens_exclude"]]
                text = f"{' '.join(bits)} {dish} recipe" + (f" ready in under {n} minutes" if n else "")
            out.append({"set": "t3", "lang": lang, "kind": "conflict", "template": text, "text": " ".join(text.split()),
                        "dish_keyword": kw, "gold": {"intent": "search", "constraints": c}})
    for vi, en in T3_OUT_OF_SCOPE:
        for lang, text in (("vi", vi), ("en", en)):
            out.append({"set": "t3", "lang": lang, "kind": "out_of_scope", "template": text, "text": text,
                        "gold": {"intent": "out_of_scope", "constraints": empty_constraints()}})
    return out


def t4_items(rng: random.Random, n: int) -> list[dict]:
    """n dialogues: the scripts cycled over languages; gold per turn is the state the user means at that turn."""
    out = []
    for i in range(n):
        script, lang = T4_SCRIPTS[i % len(T4_SCRIPTS)], ("vi", "en")[(i // len(T4_SCRIPTS)) % 2]
        li = 0 if lang == "vi" else 1
        dish, a, ing = rng.choice(DISHES), rng.choice(list(ALLERGENS)), rng.choice(INGREDIENTS)
        diet, n_min = rng.choice(list(DIETS)), rng.choice(MINUTES)
        state = empty_constraints()
        turns = []
        for vi, en, intent, change in script:
            text = (vi, en)[li].format(dish=dish[li], a=ALLERGENS[a][li], ing=ing[li], diet=DIETS[diet][li], n=n_min)
            ref = None
            for key, how in change.items():
                if key == "ref_recipe":
                    ref = how
                elif how == "+a":
                    state["allergens_exclude"] = sorted({*state["allergens_exclude"], a})
                elif how == "-a":
                    state["allergens_exclude"] = [x for x in state["allergens_exclude"] if x != a]
                elif how == "+ing":
                    state["ingredients_exclude"] = sorted({*state["ingredients_exclude"], ing[2]})
                elif how == "n":
                    state["max_total_minutes"] = n_min
                elif how == "diet":
                    state["diet"] = diet
                elif how is None:
                    state[key] = None
            gold = {"intent": intent, "constraints": json.loads(json.dumps(state))}
            if ref:
                gold["ref_recipe"] = ref
            turns.append({"text": text, "gold": gold})
        out.append({"set": "t4", "lang": lang, "kind": f"script{T4_SCRIPTS.index(script) + 1}", "turns": turns,
                    "text": " || ".join(t["text"] for t in turns), "dish_keyword": dish[2],
                    "gold": {"intent": "dialogue", "constraints": max((t["gold"]["constraints"] for t in turns),
                                                                     key=lambda c: len(json.dumps(c)))}})
    return out


# ---- filters ---------------------------------------------------------------------------------------------------

def v1_copies_title(text: str, titles: list[str]) -> bool:
    """A recipe title of 3+ words found whole in the query."""
    low = " " + " ".join(re.findall(r"[a-z0-9]+", fold(text))) + " "
    return any(f" {t} " in low for t in titles)


def tag_sql(gold: dict, keyword: str | None) -> tuple[str, list]:
    """Recipes whose title has the dish keyword and whose TAGS fit the gold (candidates the checker then reads)."""
    c = gold["constraints"]
    conds, params = ["true"], []
    if keyword:
        conds.append("r.title ILIKE %s")
        params.append(f"%{keyword}%")
    if c["allergens_exclude"]:
        conds.append("NOT (coalesce(t.allergens, '{}') && %s::text[])")
        params.append(c["allergens_exclude"])
    if c["ingredients_exclude"]:
        conds.append("NOT (coalesce(t.ingredients_norm, '{}') && %s::text[])")
        params.append(c["ingredients_exclude"])
    if c["diet"]:
        conds.append("%s = ANY(coalesce(t.diet_flags, '{}'))")
        params.append(c["diet"])
    if c["max_total_minutes"]:
        conds.append("r.total_minutes <= %s")
        params.append(c["max_total_minutes"])
    return ("SELECT r.id FROM recipe r LEFT JOIN recipe_tag t ON t.recipe_id = r.id WHERE "
            + " AND ".join(conds) + " ORDER BY md5(r.id::text || %s)", params + [str(SEED)])


def checker_constraints(gold: dict) -> list[str]:
    c = gold["constraints"]
    return ([f"allergen:{a}" for a in c["allergens_exclude"]] + [f"ingredient:{i}" for i in c["ingredients_exclude"]]
            + ([f"diet:{c['diet']}"] if c["diet"] else []))


def v2_fits(conn, check, item: dict) -> dict:
    """V2: a Recipe the independent checker passes on every constraint (time from the total_minutes column).
    `check(recipe_id, constraints) -> {constraint: verdict}`."""
    sql, params = tag_sql(item["gold"], item.get("dish_keyword"))
    ids = [r for (r,) in conn.execute(sql + " LIMIT %s", params + [V2_RECIPES])]
    cons = checker_constraints(item["gold"])
    read, errors = [], []
    for rid in ids:
        verdicts = None
        for _ in range(2):  # a checker call that times out is retried once, then that Recipe does not count
            try:
                verdicts = check(rid, cons) if cons else {}
                break
            except Exception as e:  # httpx timeouts, Ollama errors: logged in the item, never a silent pass
                errors.append(f"R{rid}: {type(e).__name__}")
        read.append(rid)
        if verdicts is None:
            continue
        if all(v.contains == "no" for v in verdicts.values()):
            return {"ok": True, "recipe_id": rid, "read": read, "errors": errors}
    return {"ok": False, "recipe_id": None, "read": read, "errors": errors}


def v2_none(conn, item: dict) -> dict:
    """V2 for T3 conflicts: SQL finds no Recipe with the dish keyword whose tags fit (out of scope: always kept)."""
    if item["gold"]["intent"] == "out_of_scope":
        return {"ok": True, "count": None}
    sql, params = tag_sql(item["gold"], item.get("dish_keyword"))
    n = conn.execute(f"SELECT count(*) FROM ({sql}) x", params).fetchone()[0]
    return {"ok": n == 0, "count": n}


def apply_filters(items: list[dict], titles: list[str], v2, kept_texts: list[str] | None = None,
                  strict_lang: bool = True) -> tuple[list[dict], Counter]:
    """V1, V3, V5 (cheap), V2 (checker), V4 (against everything kept so far). Returns kept items and counts."""
    counts: Counter = Counter()
    kept, seen = [], list(kept_texts or [])
    for it in items:
        texts = [t["text"] for t in it["turns"]] if "turns" in it else [it["text"]]
        if any(v1_copies_title(t, titles) for t in texts):
            counts["V1"] += 1
            continue
        if not all(lang_ok(t, it["lang"]) for t in texts):
            if strict_lang:
                counts["V3"] += 1
                continue
            it["v3_warning"] = True
        if not all(3 <= words(t) <= 40 for t in texts if it["set"] != "t4") or (
                it["set"] == "t4" and not all(1 <= words(t) <= 40 for t in texts)):
            counts["V5"] += 1
            continue
        if v2 is not None:
            res = v2(it)
            it["v2"] = res
            if not res["ok"]:
                counts["V2"] += 1
                continue
        if any(jaccard(texts[0], s) >= JACCARD for s in seen):
            counts["V4"] += 1
            continue
        seen.append(texts[0])
        kept.append(it)
    return kept, counts


# ---- run -------------------------------------------------------------------------------------------------------

def read_handwritten() -> list[dict]:
    if not HANDWRITTEN.exists():
        with open(HANDWRITTEN, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["set", "lang", "text", "note"])
            w.writerow(["t2", "vi", "minh di ung tom, nau gi cho bua toi nhanh duoc", "ví dụ: không dấu (xóa dòng này)"])
        return []
    out = []
    with open(HANDWRITTEN, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            text = (r.get("text") or "").strip()
            if not text or "xóa dòng này" in (r.get("note") or ""):
                continue
            item = {"set": r["set"].strip(), "lang": r["lang"].strip(), "kind": "handwritten", "source": "handwritten",
                    "text": text, "note": r.get("note", ""), "gold": None, "needs_gold": True}
            if item["set"] == "t4":
                item["turns"] = [{"text": t.strip(), "gold": None} for t in text.split("||")]
            out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if FROZEN.exists():
        sys.exit("the A3 test set is frozen (eval/testset/frozen.json): no regeneration (CLAUDE.md rule 8)")
    import httpx
    import psycopg

    import checker
    import make_patient_queries as mpq
    from api import config

    rng = random.Random(SEED)
    CAND.mkdir(parents=True, exist_ok=True)
    flow: dict = {"generated_at": datetime.now().isoformat(timespec="seconds"), "seed": SEED,
                  "paraphrase_model": None if args.no_llm else PARAPHRASE_MODEL, "checker_model": checker.CHECKER_MODEL,
                  "targets": TARGET, "sets": {}}
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=600) as client:
        mpq.load_food_words(conn)
        titles = sorted({" ".join(re.findall(r"[a-z0-9]+", fold(t))) for (t,) in conn.execute("SELECT title FROM recipe")
                         if len(re.findall(r"[a-z0-9]+", fold(t))) >= 3})
        cache = checker.load_cache()

        def check(rid, cons):
            return checker.check(conn, client, rid, cons, cache)

        def v2(item):
            return v2_none(conn, item) if item["set"] == "t3" else v2_fits(conn, check, item)

        llm = None if args.no_llm else client
        kept_texts: list[str] = []
        sets: dict[str, list[dict]] = {}

        # T1: A1 queries
        a1 = [json.loads(l) for l in (ROOT / "eval" / "queries.jsonl").read_text(encoding="utf-8").splitlines() if l]
        pool = rng.sample(a1, min(len(a1), int(TARGET["t1"] * 1.5)))
        t1 = [{"set": "t1", "lang": "en", "kind": "a1", "source": "a1", "text": q["text"], "a1_query_id": q["query_id"],
               "a1_recipe_id": q["recipe_id"], "gold": {"intent": "search", "constraints": empty_constraints()},
               "needs_gold": bool(T1_CONSTRAINT_HINT.search(q["text"]))} for q in pool]

        # T2: templates, paraphrased
        t2 = t2_items(rng, int(TARGET["t2"] * 1.6))
        for i, it in enumerate(t2):
            it["text"], it["paraphrased"] = paraphrase(llm, it["template"], it["lang"], it.pop("must"), VOICES[i % len(VOICES)])
            it["source"] = "template"

        t3 = t3_items()
        for it in t3:
            it["source"] = "template"
        t4 = t4_items(rng, int(TARGET["t4"] * 1.3))
        for it in t4:
            it["source"] = "template"

        for name, items in (("t1", t1), ("t2", t2), ("t3", t3), ("t4", t4)):
            v2_fn = None if name == "t1" else v2  # T1: A1's own queries, answered by their source Recipe
            kept, counts = apply_filters(items, titles if name != "t1" else [], v2_fn, kept_texts)
            trimmed = kept[:TARGET[name]]
            kept_texts += [it["text"].split(" || ")[0] for it in trimmed]
            sets[name] = trimmed
            flow["sets"][name] = {"generated": len(items), "rejected": {k: counts.get(k, 0) for k in ("V1", "V2", "V3", "V4", "V5")},
                                  "kept": len(kept), "trimmed_to_target": len(kept) - len(trimmed), "candidates": len(trimmed)}
            errs = sum(len((it.get("v2") or {}).get("errors", [])) for it in items)
            if errs:  # checker calls that failed twice: those Recipes did not count for V2
                flow["sets"][name]["v2_checker_errors"] = errs
            if name == "t2":
                flow["sets"][name]["paraphrased"] = sum(bool(it.get("paraphrased")) for it in trimmed)
                flow["sets"][name]["by_lang"] = dict(Counter(it["lang"] for it in trimmed))
            if name == "t1":
                flow["sets"][name]["needs_gold"] = sum(it["needs_gold"] for it in trimmed)

        hand = read_handwritten()
        kept_h, counts_h = apply_filters(hand, titles, None, kept_texts, strict_lang=False)
        flow["handwritten"] = {"rows": len(hand), "rejected": {k: counts_h.get(k, 0) for k in ("V1", "V4", "V5")},
                               "kept": len(kept_h), "v3_warnings": sum(bool(it.get("v3_warning")) for it in kept_h)}
        for it in kept_h:
            sets[it["set"]].append(it)

    for name, items in sets.items():
        for i, it in enumerate(items, 1):
            it["id"] = f"{name}_{i:03d}"
        (CAND / f"{name}.jsonl").write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items),
                                            encoding="utf-8")
    (OUT / "testset_flow.json").write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(flow["sets"], ensure_ascii=False, indent=1))
    print("handwritten:", flow["handwritten"])


if __name__ == "__main__":
    main()
