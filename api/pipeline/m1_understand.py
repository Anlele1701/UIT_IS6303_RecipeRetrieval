"""M1 query understanding: intent, language, constraints and a standalone English query (6.1, plus `remove`).

qwen2.5:7b fills a flat JSON schema (sentinels instead of nulls: small models handle them better); then a
deterministic pass keeps only known allergen codes, maps ingredient names to canonical ones (Vietnamese via
ingredient_alias_vi, English via the ingredient lexicon), drops what the lexicon does not know (noted in the
trace), strips negations from query_en ([S12]: negation goes to WHERE, not to the embedding) and detects the
language by rule. Ambiguous Vietnamese words: `context` ones are spelled out to the model ("bơ = butter or
avocado"), `ask` ones make the assistant ask back (Thy, M1). If the reply is not usable twice, a keyword
fallback keeps the turn going.
"""

import re

import httpx

from ..textmatch import looks_vietnamese, unaccent
from .lexicon import RuntimeLexicon, norm, valid_allergens
from .llm import LLMError, chat_json
from .schemas import ALLERGENS, DIETS, Constraints, Removal, Understanding

INTENTS = ["search", "refine", "ask_detail", "out_of_scope", "chitchat"]
LASTING = ["allergens", "ingredients_exclude", "diet", "max_total_minutes"]
SCHEMA = {"type": "object", "required": ["intent", "query_en", "allergens_exclude", "ingredients_exclude",
                                         "ingredients_include", "diet", "max_total_minutes", "lasting",
                                         "remove_allergens", "remove_ingredients", "remove_diet", "remove_time",
                                         "ref_recipe"],
          "properties": {
              "intent": {"type": "string", "enum": INTENTS},
              "query_en": {"type": "string"},
              "allergens_exclude": {"type": "array", "items": {"type": "string", "enum": ALLERGENS}},
              "ingredients_exclude": {"type": "array", "items": {"type": "string"}},
              "ingredients_include": {"type": "array", "items": {"type": "string"}},
              "diet": {"type": "string", "enum": ["none", *DIETS]},
              "max_total_minutes": {"type": "integer"},
              "lasting": {"type": "array", "items": {"type": "string", "enum": LASTING}},
              "remove_allergens": {"type": "array", "items": {"type": "string", "enum": ALLERGENS}},
              "remove_ingredients": {"type": "array", "items": {"type": "string"}},
              "remove_diet": {"type": "boolean"},
              "remove_time": {"type": "boolean"},
              "ref_recipe": {"type": "integer"}}}

SYSTEM = """You turn one message of a cooking-assistant chat (Vietnamese or English) into JSON for a recipe search.
The recipe collection is in English. Rules:
- intent: "search" (a new request), "refine" (adds to or changes the previous request: "thêm điều kiện…",
  "make it faster", "what about without dairy"), "ask_detail" (about a dish already shown: "món thứ 2 làm thế nào",
  "how long does the first one take"), "chitchat" (greetings, thanks), "out_of_scope" (not about cooking).
- query_en: what the user wants to cook, in English, standalone (resolve "it", "món đó" from the conversation),
  WITHOUT any negation or restriction: "no peanuts" or "không có sữa" never go into query_en.
- allergens_exclude: allergy groups the user must avoid, from the allowed codes only (dị ứng / allergic / không ăn được).
  milk = dairy; tree_nuts = almonds, walnuts, cashews...; crustacean_shellfish = shrimp, crab, lobster.
- ingredients_exclude: other ingredients the user does not want, in English ("không ngò" -> "cilantro").
- ingredients_include: ingredients the user wants to use, in English.
- diet: "vegetarian" (chay, không thịt cá), "vegan" (thuần chay), else "none".
- max_total_minutes: a time limit in minutes ("dưới 30 phút", "within an hour" -> 60), else 0.
- lasting: constraint types the user says hold from now on ("từ giờ", "luôn luôn", "from now on").
- remove_*: constraints the user lifts ("giờ ăn được đậu phộng rồi" -> remove_allergens ["peanut"]).
- ref_recipe: for ask_detail, the position of the dish in the last answer (1 = first), else 0.
Leave every list empty and every number 0 unless the message itself asks for it.
Answer with JSON only.

Examples:
Message: "Tôi dị ứng đậu phộng, gợi ý món tráng miệng dưới 30 phút"
{"intent":"search","query_en":"dessert","allergens_exclude":["peanut"],"ingredients_exclude":[],"ingredients_include":[],
 "diet":"none","max_total_minutes":30,"lasting":[],"remove_allergens":[],"remove_ingredients":[],"remove_diet":false,
 "remove_time":false,"ref_recipe":0}
Message: "mon ga nuong khong co ngo"
{"intent":"search","query_en":"roast chicken","allergens_exclude":[],"ingredients_exclude":["cilantro"],
 "ingredients_include":[],"diet":"none","max_total_minutes":0,"lasting":[],"remove_allergens":[],"remove_ingredients":[],
 "remove_diet":false,"remove_time":false,"ref_recipe":0}
Message: "giờ ăn được đậu phộng rồi"
{"intent":"refine","query_en":"","allergens_exclude":[],"ingredients_exclude":[],"ingredients_include":[],
 "diet":"none","max_total_minutes":0,"lasting":[],"remove_allergens":["peanut"],"remove_ingredients":[],
 "remove_diet":false,"remove_time":false,"ref_recipe":0}
Message: "vegan curry, ready within an hour"
{"intent":"search","query_en":"curry","allergens_exclude":[],"ingredients_exclude":[],"ingredients_include":[],
 "diet":"vegan","max_total_minutes":60,"lasting":[],"remove_allergens":[],"remove_ingredients":[],"remove_diet":false,
 "remove_time":false,"ref_recipe":0}"""


# Patient sessions only (MV3): the same schema plus needs_record_context and the patient_info intent. A session
# without a patient keeps SCHEMA and SYSTEM byte for byte, so its cached replies (data/cache/llm.jsonl) still hold.
INTENTS_PATIENT = [*INTENTS, "patient_info"]
SCHEMA_PATIENT = {**SCHEMA, "required": [*SCHEMA["required"], "needs_record_context"],
                  "properties": {**SCHEMA["properties"], "intent": {"type": "string", "enum": INTENTS_PATIENT},
                                 "needs_record_context": {"type": "boolean"}}}
SYSTEM_PATIENT = SYSTEM.replace("Answer with JSON only.", """The chat is about one patient whose medical record the assistant can read.
- intent "patient_info": a question about the patient's record itself, not a recipe request
  ("bệnh nhân này dị ứng gì?", "what medications is the patient on?").
- needs_record_context: true when answering needs the patient's history (past visits, lab results by year:
  "lần khám gần nhất có gì liên quan ăn uống không", "were the last blood tests normal?"); else false.
  Allergies, current problems, current medications and latest vital signs are always available: they need no context.
Answer with JSON only.""") + """
Message: "gợi ý món tối nhanh cho bệnh nhân này"
{"intent":"search","query_en":"quick dinner","allergens_exclude":[],"ingredients_exclude":[],"ingredients_include":[],
 "diet":"none","max_total_minutes":0,"lasting":[],"remove_allergens":[],"remove_ingredients":[],"remove_diet":false,
 "remove_time":false,"ref_recipe":0,"needs_record_context":false}
Message: "lần xét nghiệm gần nhất của bệnh nhân có gì cần lưu ý khi ăn uống không?"
{"intent":"patient_info","query_en":"","allergens_exclude":[],"ingredients_exclude":[],"ingredients_include":[],
 "diet":"none","max_total_minutes":0,"lasting":[],"remove_allergens":[],"remove_ingredients":[],"remove_diet":false,
 "remove_time":false,"ref_recipe":0,"needs_record_context":true}"""


def detect_lang(message: str) -> str:
    return "vi" if looks_vietnamese(message) else "en"


def build_messages(message: str, history: list[dict], current: Constraints, hints: list[tuple],
                   system: str = SYSTEM) -> list[dict]:
    ctx = []
    if history:
        ctx.append("Conversation so far:\n" + "\n".join(f"{h['role']}: {h['content'][:400]}" for h in history))
    if not current.is_empty():
        ctx.append("Constraints already active: " + current.model_dump_json(exclude_defaults=True))
    for word, alias in hints:
        if alias.resolve == "context":
            ctx.append(f'The word "{word}" can mean {" or ".join(alias.ingredients)}: pick the one the dish implies.')
    user = ("\n\n".join(ctx) + "\n\n" if ctx else "") + f"Message: {message}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


NEGATION = re.compile(r"\b(?:without|no|not|free of|minus|except|excluding|avoid(?:ing)?)\b[^,.;]*", re.I)


def strip_negation(q: str) -> str:
    return re.sub(r"\s+", " ", NEGATION.sub(" ", q)).strip(" ,.;")


# English words that ground an allergen code in the message (Vietnamese ones come from ingredient_alias_vi).
ALLERGEN_WORDS = {
    "milk": ["milk", "dairy", "lactose", "cheese", "butter", "cream", "yogurt"],
    "egg": ["egg"], "fish": ["fish", "anchov", "salmon", "tuna", "cod"],
    "crustacean_shellfish": ["shellfish", "shrimp", "prawn", "crab", "lobster", "crustacean"],
    "tree_nuts": ["tree nut", "nut", "almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut"],
    "peanut": ["peanut"], "wheat": ["wheat", "gluten", "flour"], "soy": ["soy", "tofu"], "sesame": ["sesame", "tahini"],
}
REMOVAL_CUES = re.compile(r"ăn được|an duoc|hết dị ứng|het di ung|không còn|khong con|bỏ điều kiện|bo dieu kien|bỏ qua|"
                          r"gỡ|go bo|cho phép|cho phep|no longer|can eat|is fine now|okay with|ok with|remove|drop the|"
                          r"allow", re.I)


def named(alias: str, text: str) -> bool:
    """The alias as whole words in the text, with or without diacritics."""
    pat = rf"(?<!\w){re.escape(alias)}(?!\w)"
    return bool(re.search(pat, text) or re.search(rf"(?<!\w){re.escape(unaccent(alias))}(?!\w)", unaccent(text)))


def grounded_allergen(code: str, message: str, lex: RuntimeLexicon) -> bool:
    text = norm(message)
    if any(w in unaccent(text) for w in ALLERGEN_WORDS[code]):
        return True
    return any(code in a.allergens and named(alias, text) for alias, a in lex.aliases.items())


def grounded_ingredient(canonical: str, message: str, lex: RuntimeLexicon) -> bool:
    text = norm(message)
    toks = set(re.findall(r"[a-z]+", unaccent(text)))
    if all(w in toks or w + "s" in toks or w + "es" in toks for w in canonical.split()):
        return True
    return any(canonical in a.ingredients and named(alias, text) for alias, a in lex.aliases.items())


def keep_grounded(items: list[str], message: str, lex: RuntimeLexicon, notes: list[str], what: str, test) -> list[str]:
    kept = [i for i in items if test(i, message, lex)]
    if len(kept) < len(items):
        notes.append(f"dropped {what} not named in the message: {sorted(set(items) - set(kept))}")
    return kept


VEGAN_CUE = re.compile(r"thuần chay|thuan chay|\bvegan\b|plant[- ]based", re.I)
GENERIC_NUT = re.compile(r"(?<!tree )\bnuts?\b(?!\s*(?:milk|meg))", re.I)  # "nut-free", "no nuts"; not "tree nuts"
TIME_CUE = re.compile(r"\d|phút|phut|giờ|gio|tiếng|tieng|minute|min\b|hour|hr\b", re.I)
RULE_TRIGGER = re.compile(r"(?:dị ứng|di ung|không có|khong co|không|khong|kiêng|kieng|allergic to|allergy to|"
                          r"\bno\b|without|free of)\s+([^,.;!?]+)", re.I)


def lifted_codes(raw: dict, removing: bool, rem_codes: list[str] | None = None) -> set[str]:
    return set(valid_allergens([*raw.get("remove_allergens", []), *(rem_codes or [])])) if removing else set()


def rule_constraints(message: str, lex: RuntimeLexicon) -> Constraints:
    """Exact aliases or allergen words right after a negation/allergy cue: catches what the model skipped."""
    codes, ings = [], []
    for phrase in RULE_TRIGGER.findall(norm(message)):
        toks = phrase.split()
        for n in range(min(4, len(toks)), 0, -1):
            a = lex.vi(" ".join(toks[:n]))
            if a:
                codes += a.allergens
                ings += a.ingredients
                break
        else:
            head = " ".join(toks[:2])
            codes += [c for c, ws in ALLERGEN_WORDS.items() if any(head.startswith(w) for w in ws)]
    return Constraints(allergens_exclude=valid_allergens(codes), ingredients_exclude=list(dict.fromkeys(ings)))


def map_ingredients(names: list[str], lex: RuntimeLexicon, notes: list[str]) -> tuple[list[str], list[str]]:
    """English or Vietnamese names -> (canonical ingredients, allergen codes an alias points to)."""
    ings, codes = [], []
    for name in names:
        a = lex.vi(name)
        if a:
            ings += list(a.ingredients)  # "hải sản" -> fish and crustacean codes plus the molluscs
            codes += list(a.allergens)
            continue
        found = lex.to_canonical(name)
        if found:
            ings += found
        else:
            notes.append(f"dropped unknown ingredient {name!r}")
    return list(dict.fromkeys(ings)), codes


# Wanted qualities the model tends to drop from query_en as "restrictions" (pe03): patient sessions put them back.
# The dialogue has no nutrient constraint yet: the phrase only steers the search text (a limitation, progress MV3).
QUALITY_CUES = [(re.compile(p, re.I), phrase) for p, phrase in [
    (r"low[- ]?salt|low[- ]?sodium|ít muối|it muoi|giảm muối|giam muoi|nhạt muối", "low-sodium"),
    (r"low[- ]?fat|ít béo|it beo|ít dầu mỡ", "low-fat"),
    (r"low[- ]?sugar|ít đường|it duong|không đường", "low-sugar"),
    (r"high[- ]?fiber|nhiều chất xơ|nhieu chat xo", "high-fiber")]]


# Waving a constraint away without the usual words (pv06 "cứ cho món có tôm đi, không sao đâu"). Patient sessions
# only, where M2 refuses to lift a record constraint and says so; the M3 path keeps REMOVAL_CUES alone.
PATIENT_REMOVAL_CUES = re.compile(r"không sao|khong sao|cứ cho|cu cho|không vấn đề|khong van de|không có gì đâu|"
                                  r"it's fine|it is fine|no problem|don't worry|go ahead", re.I)


def lift_named(u: Understanding, message: str, lex: RuntimeLexicon, current: Constraints) -> Understanding:
    """Patient sessions: a removal cue plus an allergen in force that the message names is a request to lift it,
    even when the model returns no remove_* (pv06, MV3 demo). M2 refuses it for a record allergy and says so."""
    if not (REMOVAL_CUES.search(message) or PATIENT_REMOVAL_CUES.search(message)):
        return u
    named_now = [a for a in current.allergens_exclude
                 if a not in u.remove.allergens and grounded_allergen(a, message, lex)]
    if not named_now:
        return u
    u.remove.allergens = valid_allergens([*u.remove.allergens, *named_now])
    u.constraints.allergens_exclude = [a for a in u.constraints.allergens_exclude if a not in named_now]
    u.notes.append(f"lift request by rule: allergens {named_now} are named next to a removal cue")
    if u.intent == "search":
        u.intent = "refine"
    return u


def keep_qualities(query: str, message: str, notes: list[str]) -> str:
    missing = [phrase for rx, phrase in QUALITY_CUES if rx.search(message) and not rx.search(query)
               and phrase not in query]
    if missing:
        notes.append(f"kept wanted qualities the model dropped from query_en: {missing}")
        return " ".join([*missing, query]).strip()
    return query


def postprocess(raw: dict, message: str, lex: RuntimeLexicon, patient: bool = False) -> Understanding:
    """The model's JSON -> a validated Understanding. Pure, so it is unit-tested without a model."""
    notes: list[str] = []
    excl, excl_codes = map_ingredients(raw.get("ingredients_exclude", []), lex, notes)
    incl, _ = map_ingredients(raw.get("ingredients_include", []), lex, notes)
    excl = keep_grounded(excl, message, lex, notes, "excluded ingredients", grounded_ingredient)
    incl = keep_grounded(incl, message, lex, notes, "included ingredients", grounded_ingredient)
    allergens = valid_allergens([*raw.get("allergens_exclude", []), *excl_codes])
    dropped = set(raw.get("allergens_exclude", [])) - set(ALLERGENS)
    if dropped:
        notes.append(f"dropped unknown allergen codes {sorted(dropped)}")
    allergens = keep_grounded(allergens, message, lex, notes, "allergens", grounded_allergen)
    if set(incl) & set(excl):
        notes.append(f"include and exclude both name {sorted(set(incl) & set(excl))}: exclude wins")
        incl = [i for i in incl if i not in excl]
    diet = raw.get("diet") if raw.get("diet") in DIETS else None
    minutes = raw.get("max_total_minutes") or None
    query = strip_negation(raw.get("query_en", "")) or (message if detect_lang(message) == "en" else "")
    if patient:  # patient sessions only: the M3 path stays exactly as it was (no-patient regression)
        query = keep_qualities(query, message, notes)
    rem_ing, rem_codes = map_ingredients(raw.get("remove_ingredients", []), lex, notes)
    removing = bool(REMOVAL_CUES.search(message) or (patient and PATIENT_REMOVAL_CUES.search(message)))
    if not removing and (raw.get("remove_allergens") or rem_ing or raw.get("remove_diet") or raw.get("remove_time")):
        notes.append("ignored remove_* without a removal cue in the message")
        raw = {**raw, "remove_allergens": [], "remove_diet": False, "remove_time": False}
        rem_ing, rem_codes = [], []
    if removing:  # "giờ ăn được đậu phộng" lifts peanut: it must not be excluded again in the same turn
        allergens = [a for a in allergens if a not in lifted_codes(raw, removing, rem_codes)]
    rule = rule_constraints(message, lex)
    added = [a for a in rule.allergens_exclude if a not in allergens and a not in lifted_codes(raw, removing)]
    if added:
        notes.append(f"added from the message by rule: allergens {added}")
        allergens = valid_allergens(allergens + added)
    more = [i for i in rule.ingredients_exclude if i not in excl and i not in rem_ing]
    if more:
        notes.append(f"added from the message by rule: excluded ingredients {more}")
        excl += more
    if minutes and not TIME_CUE.search(message):
        notes.append(f"dropped a {minutes}-minute limit the message does not state")
        minutes = None
    if diet == "vegetarian" and VEGAN_CUE.search(message):
        notes.append("diet set to vegan: the message says vegan / thuần chay")
        diet = "vegan"
    if "tree_nuts" in allergens and "peanut" not in allergens and GENERIC_NUT.search(message) \
            and "peanut" not in lifted_codes(raw, removing, rem_codes):
        notes.append("added peanut: a plain 'nut' covers peanuts too (safe side)")
        allergens = valid_allergens(allergens + ["peanut"])
    u = Understanding(
        intent=raw.get("intent") if raw.get("intent") in (INTENTS_PATIENT if patient else INTENTS) else "search",
        needs_record_context=bool(raw.get("needs_record_context")) if patient else False,
        lang=detect_lang(message), query_en=query,
        constraints=Constraints(allergens_exclude=allergens, ingredients_exclude=excl, ingredients_include=incl,
                                diet=diet, max_total_minutes=minutes if minutes and minutes > 0 else None),
        session_scope=[s for s in raw.get("lasting", []) if s in LASTING],
        remove=Removal(allergens=valid_allergens([*raw.get("remove_allergens", []), *rem_codes]),
                       ingredients=rem_ing, diet=bool(raw.get("remove_diet")),
                       max_total_minutes=bool(raw.get("remove_time"))),
        ref_recipe=raw.get("ref_recipe") or None, notes=notes)
    return u


def ask_back(message: str, lex: RuntimeLexicon, u: Understanding) -> str | None:
    """An `ask` word (hành) used as a constraint, without the precise form (hành lá…): the question to ask."""
    for word, alias in lex.hints(message):
        if alias.resolve != "ask":
            continue
        if not precise(message, word, lex):
            options = ", ".join(alias.ingredients)
            return (f'"{word}" có thể là {options}. Bạn muốn nói loại nào?' if u.lang == "vi"
                    else f'"{word}" could mean {options}. Which one do you mean?')
    return None


def precise(message: str, word: str, lex: RuntimeLexicon) -> bool:
    """True when every occurrence of `word` is part of a longer, unambiguous alias ("hành lá")."""
    text = norm(message)
    longer = [a for a in lex.aliases if a != word and a.startswith(word + " ") and lex.aliases[a].resolve == "fixed"]
    rest = text
    for a in sorted(longer, key=len, reverse=True):
        rest = re.sub(rf"(?<!\w){re.escape(a)}(?!\w)", " ", rest)
    return not re.search(rf"(?<!\w){re.escape(word)}(?!\w)", rest)


FALLBACK_TRIGGERS = re.compile(r"\b(dị ứng|di ung|không|khong|allergic to|allergy|no|without)\s+([^,.;!?]+)", re.I)


def fallback(message: str, lex: RuntimeLexicon) -> Understanding:
    """Keyword rules when the model fails twice: aliases after 'dị ứng / không / no / without'."""
    codes, ings = [], []
    for _, phrase in FALLBACK_TRIGGERS.findall(message):
        for n in range(len(phrase.split()), 0, -1):
            a = lex.vi(" ".join(phrase.split()[:n]))
            if a:
                codes += a.allergens
                ings += a.ingredients
                break
        else:
            ings += lex.to_canonical(phrase)
    lang = detect_lang(message)
    return Understanding(intent="search", lang=lang, query_en=strip_negation(message) if lang == "en" else unaccent(message),
                         constraints=Constraints(allergens_exclude=valid_allergens(codes), ingredients_exclude=ings),
                         notes=["model reply unusable twice: keyword fallback"])


def understand(client: httpx.Client, lex: RuntimeLexicon, message: str, history: list[dict],
               current: Constraints, patient: bool = False) -> Understanding:
    """patient=True (a session about a patient record) uses SCHEMA_PATIENT and SYSTEM_PATIENT; otherwise the
    call is exactly the M3 one, cache key included."""
    schema, system = (SCHEMA_PATIENT, SYSTEM_PATIENT) if patient else (SCHEMA, SYSTEM)
    messages = build_messages(message, history, current, lex.hints(message), system)
    for attempt in range(2):
        try:
            raw = chat_json(client, schema, messages, use_cache=attempt == 0)
            if isinstance(raw, dict) and "intent" in raw:
                u = postprocess(raw, message, lex, patient)
                if patient:
                    u = lift_named(u, message, lex, current)
                u.clarify = ask_back(message, lex, u)
                return u
        except (LLMError, httpx.HTTPError):
            pass
    return fallback(message, lex)
