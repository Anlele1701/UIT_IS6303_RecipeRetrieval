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


def detect_lang(message: str) -> str:
    return "vi" if looks_vietnamese(message) else "en"


def build_messages(message: str, history: list[dict], current: Constraints, hints: list[tuple]) -> list[dict]:
    ctx = []
    if history:
        ctx.append("Conversation so far:\n" + "\n".join(f"{h['role']}: {h['content'][:400]}" for h in history))
    if not current.is_empty():
        ctx.append("Constraints already active: " + current.model_dump_json(exclude_defaults=True))
    for word, alias in hints:
        if alias.resolve == "context":
            ctx.append(f'The word "{word}" can mean {" or ".join(alias.ingredients)}: pick the one the dish implies.')
    user = ("\n\n".join(ctx) + "\n\n" if ctx else "") + f"Message: {message}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


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


def postprocess(raw: dict, message: str, lex: RuntimeLexicon) -> Understanding:
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
    rem_ing, rem_codes = map_ingredients(raw.get("remove_ingredients", []), lex, notes)
    removing = bool(REMOVAL_CUES.search(message))
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
    u = Understanding(
        intent=raw.get("intent") if raw.get("intent") in INTENTS else "search",
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
               current: Constraints) -> Understanding:
    messages = build_messages(message, history, current, lex.hints(message))
    for attempt in range(2):
        try:
            raw = chat_json(client, SCHEMA, messages, use_cache=attempt == 0)
            if isinstance(raw, dict) and "intent" in raw:
                u = postprocess(raw, message, lex)
                u.clarify = ask_back(message, lex, u)
                return u
        except (LLMError, httpx.HTTPError):
            pass
    return fallback(message, lex)
