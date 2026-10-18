"""M7 citation check (sườn báo cáo 3.4): every [R<id>] must be a context Recipe that keeps the definite constraints.

A citation outside the context, or to a Recipe whose definite tags break an allergen, ingredient or diet
constraint, is removed. Possible tags never count as a break (they are warnings, Thy M1). When any citation was
removed (valid-citation rate below 1), the orchestrator regenerates once. An answer citing nothing passes: an
honest "nothing fits" must not be pushed into citing a Recipe.

Patient sessions (MV3, spec 5.6) add three checks, all leading to the same single regeneration:
(a) a cited Recipe whose per-serving value breaks a record nutrient limit is removed (an unknown value is not
    a break: unknown_strict decides that in M4);
(b) the text must not suggest an ingredient the patient must avoid: an excluded ingredient or allergen word that
    is not negated or flagged as a warning nearby (English and the Vietnamese aliases of the lexicon);
(c) every [H:<node_id>] must name a node of the patient's tree; others are removed;
(d) route patient_info only: every number in the answer must match a value in the facts of the nodes read
    (at the precision written), so the answer cannot invent or derive a measurement; a sentence holding a number
    must not interpret it ("normal", "elevated", "cao"...; the record's condition names are masked first); and the
    answer must not copy the data blocks (RECORD, PATIENT_PROFILE) back. When the one regeneration still fails,
    the orchestrator answers with the values listed by code (values_answer) and traces it.
Without a patient context, verify() is exactly the M3 check.
"""

import re
from dataclasses import dataclass, field

from ..patient.nutrition import meets
from ..textmatch import looks_vietnamese
from .schemas import Constraints, RecipeCard, Verification

CITE = re.compile(r"\[R(\d+)\]")
CITE_H = re.compile(r"\[H:([^\]\s]+)\]")
# words that make a mention safe: "không có tôm", "no shrimp", "may contain milk", "dị ứng sữa"
SAFE_BEFORE = re.compile(r"(không|khong|chẳng|tránh|tranh|kiêng|kieng|thay|dị ứng|di ung|không chứa|có thể chứa|"
                         r"\bno\b|\bnot\b|without|avoid|free|instead of|replace|swap|allerg|may contain|"
                         r"check|substitut)[^.;!?\n]{0,40}$", re.I)
SAFE_AFTER = re.compile(r"^[^.;!?\n]{0,12}(-free|free\b)", re.I)


NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")
LIST_MARK = re.compile(r"^\s*\d+[.)]\s", re.M)
ECHO = re.compile(r"</?patient_profile>|PATIENT_PROFILE:|</?record>|RECORD:", re.I)
# route patient_info (Thy, after MV3): words that interpret a value. Checked only in sentences holding a number,
# after the record's condition names are masked ("tăng huyết áp" names a condition, it does not interpret).
INTERPRET = re.compile(r"(?<!\w)(normal|abnormal|elevated|high|low|increased|decreased|raised|reduced|borderline|"
                       r"within range|out of range|in range|healthy|concerning|worrying|good|bad|"
                       r"bình thường|bất thường|cao|thấp|tăng|giảm|vượt|ổn định|ổn|tốt|xấu|đáng lo)(?!\w)", re.I)
# Vietnamese names of the conditions a rule names: masked like the record's own (English) names
CONDITION_NAMES_VI = ["tăng huyết áp", "cao huyết áp", "huyết áp cao", "tiểu đường", "đái tháo đường",
                      "bệnh thận mạn", "suy thận", "đường huyết cao", "tăng đường huyết"]
SENTENCE = re.compile(r"(?:[^.!?\n]|\.(?=\d))+[.!?]?")  # "67.68" stays in one sentence
# Group words the text check also catches (Thy, after MV3): the Vietnamese aliases in "all" mode come from the
# lexicon ("hải sản"); these are the ones it lacks. Used by M7 only, never by the tagger.
GROUP_WORDS = {"crustacean_shellfish": ["shellfish", "seafood", "đồ biển", "do bien"],
               "fish": ["seafood", "đồ biển", "do bien"]}


@dataclass
class NumberIndex:
    """What numbers a patient_info answer may state (Thy, after MV3): a number written with a unit must match a
    fact value with that unit; a number without a unit must be a date part or a count taken from the nodes read."""
    by_unit: dict[str, set[float]] = field(default_factory=dict)  # lowercased unit -> values
    unitless: set[float] = field(default_factory=set)  # date parts, counts, values recorded without a unit

    @property
    def units(self) -> list[str]:
        return sorted(self.by_unit, key=len, reverse=True)


def _dates(value: str) -> set[float]:
    return {float(x) for d in re.findall(r"\d{4}-\d{2}(?:-\d{2})?", value) for x in d.split("-")}


def number_index(views: list[dict]) -> NumberIndex:
    idx = NumberIndex()
    counts: dict[str, int] = {}

    def value(v, unit):
        try:
            x = float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return
        if unit:
            idx.by_unit.setdefault(str(unit).lower(), set()).add(x)
        else:
            idx.unitless.add(x)

    def walk(f):
        if isinstance(f, dict):
            if "value" in f:
                value(f.get("value"), f.get("unit"))
            for k, v in f.items():
                if isinstance(v, str) and k in {"date", "month", "record_date"}:
                    idx.unitless |= _dates(v)
                elif isinstance(v, list | dict):
                    walk(v)
        elif isinstance(f, list):
            for x in f:
                walk(x)

    total = obs = 0
    for v in views:
        facts = v.get("facts") or []
        walk(facts)
        idx.unitless |= {float(y) for y in re.findall(r"\.(\d{4})$", v.get("node_id", ""))}  # the node's year
        idx.unitless.add(float(len(facts)))
        if v.get("node_id", "").startswith(("results.", "encounters.")):
            total += len(facts)
        for f in facts:
            name = f.get("display") or f.get("class")
            if name:
                counts[name] = counts.get(name, 0) + 1
            obs += len(f.get("observations") or [])
            for o in [f, *(f.get("observations") or [])]:  # numbers inside names: "Basic metabolic 2000 panel"
                idx.unitless |= {float(x) for x in re.findall(r"\d+(?:\.\d+)?", o.get("display") or "")}
    idx.unitless |= {float(total), float(obs), float(len(views))} | {float(n) for n in counts.values()}
    return idx


@dataclass
class PatientCheck:
    node_ids: set[str]  # every node of the patient's tree: [H:..] must name one
    avoid_terms: dict[str, list[str]] = field(default_factory=dict)  # constraint -> words that name it
    numbers: NumberIndex | None = None  # route patient_info: every number the answer may state (facts read)
    condition_names: list[str] = field(default_factory=list)  # route patient_info: masked before INTERPRET
    lang: str | None = None  # route patient_info: the answer must be in the question's language


def numbers_in(value) -> set[float]:
    """Every number written in a JSON-like value (strings included: "2026-08-16" gives 2026, 8, 16)."""
    out: set[float] = set()
    if isinstance(value, dict):
        for v in value.values():
            out |= numbers_in(v)
    elif isinstance(value, list | tuple):
        for v in value:
            out |= numbers_in(v)
    elif isinstance(value, bool) or value is None:
        pass
    elif isinstance(value, int | float):
        out.add(float(value))
    else:
        out |= {float(m.replace(",", ".")) for m in re.findall(r"\d+(?:\.\d+)?", str(value))}
    return out


def unknown_numbers(answer: str, allowed) -> list[str]:
    """Numbers in the answer that match no allowed value, at the precision the answer writes them
    ("67.7" matches 67.68). Citation marks and list numbering are not numbers of the record.

    `allowed` is a NumberIndex (a number followed by a recorded unit must match a value with that unit; any other
    number must be a date part or a count from the nodes read), or a plain set of values (no unit check)."""
    text = LIST_MARK.sub(" ", re.sub(r"\[(?:R\d+|H:[^\]]+)\]", " ", answer))
    tags = {}
    if isinstance(allowed, NumberIndex):  # units may hold digits ("10*3/uL"): swap each for a digit-free tag first
        for i, u in enumerate(allowed.units):
            tag = f"§{chr(65 + i % 26) * (1 + i // 26)}§"
            tags[tag] = u
            text = re.sub(re.escape(u), " " + tag, text, flags=re.I)
    bad = []
    for m in NUMBER.finditer(text):
        token = m.group(0)
        x = float(token.replace(",", "."))
        decimals = len(re.split(r"[.,]", token)[1]) if re.search(r"[.,]", token) else 0
        tol = 0.5 * 10 ** -decimals + 1e-9
        if isinstance(allowed, NumberIndex):
            after = text[m.end():].lstrip()
            unit = next((u for t, u in tags.items() if after.startswith(t)), None)
            pool = allowed.by_unit[unit] if unit else allowed.unitless
        else:
            pool = allowed
        if not any(abs(a - x) <= tol for a in pool):
            bad.append(token)
    return list(dict.fromkeys(bad))


def wrong_language(answer: str, lang: str) -> bool:
    """A Vietnamese question answered in English, or the reverse (codes and citations ignored)."""
    text = re.sub(r"\[(?:R\d+|H:[^\]]+)\]", " ", answer)
    return looks_vietnamese(text) != (lang == "vi")


def mask(text: str, phrases) -> str:
    """Blank out each phrase (case-insensitive, verbatim), longest first, so words inside it are not checked."""
    for ph in sorted({p for p in phrases if p}, key=len, reverse=True):
        text = re.sub(re.escape(ph), " ", text, flags=re.I)
    return text


def interpretations(answer: str, condition_names: list[str]) -> list[str]:
    """Interpreting words in the sentences that hold a number, the record's condition names masked first."""
    text = mask(re.sub(r"\[(?:R\d+|H:[^\]]+)\]", " ", answer), [*condition_names, *CONDITION_NAMES_VI])
    found = []
    for sentence in SENTENCE.findall(text):
        if NUMBER.search(LIST_MARK.sub(" ", sentence)):
            found += [m.lower() for m in INTERPRET.findall(sentence)]
    return list(dict.fromkeys(found))


def violations(card: RecipeCard, c: Constraints) -> list[str]:
    out = [f"allergen:{a}" for a in c.allergens_exclude if a in card.allergens]
    out += [f"ingredient:{i}" for i in c.ingredients_exclude if i in card.ingredients_norm]
    if c.diet and c.diet not in card.diet_flags:
        out.append(f"diet:{c.diet}")
    for col, (op, limit) in c.nutrient_limits.items():  # patient limits only (empty otherwise)
        if meets(card.nutrients.get(col), op, limit) is False:
            out.append(f"nutrient:{col}")
    return out


def cited(answer: str) -> list[int]:
    return list(dict.fromkeys(int(m) for m in CITE.findall(answer)))


def suggested_avoided(answer: str, terms: dict[str, list[str]]) -> list[str]:
    """Constraints whose words the answer uses without a negation or a warning next to them."""
    found = []
    low = answer.lower()
    for key, words in terms.items():
        for w in words:
            for m in re.finditer(rf"(?<!\w){re.escape(w.lower())}(?!\w)", low):
                if SAFE_BEFORE.search(low[:m.start()]) or SAFE_AFTER.search(low[m.end():]):
                    continue
                found.append(key)
                break
            if key in found:
                break
    return found


def verify(answer: str, cards: list[RecipeCard], c: Constraints, patient: PatientCheck | None = None) -> Verification:
    by_id = {r.id: r for r in cards}
    ids = cited(answer)
    removed = [i for i in ids if i not in by_id or violations(by_id[i], c)]
    kept = [i for i in ids if i not in removed]
    if patient is None:
        return Verification(verified=not removed, citations=kept, removed=removed)
    bad_h = [h for h in dict.fromkeys(CITE_H.findall(answer)) if h not in patient.node_ids]
    # (b) on the text only: the cited Recipes' titles and the [R..] marks are masked verbatim (Thy, after MV3); a
    # Recipe itself is checked by its tags and the checker, so "Shrimp Scampi" breaking a constraint is caught there
    flags = [f"text:{k}" for k in suggested_avoided(text_of(answer, cards), patient.avoid_terms)]
    flags += [f"node:{h}" for h in bad_h]
    if patient.numbers is not None:  # route patient_info: every number must come from a fact read (Thy, after MV3)
        flags += [f"number:{n}" for n in unknown_numbers(answer, patient.numbers)]
        flags += [f"interpret:{w}" for w in interpretations(answer, patient.condition_names)]
        if ECHO.search(answer):  # the data blocks copied back instead of an answer
            flags.append("echo:prompt_block")
        if patient.lang and wrong_language(answer, patient.lang):
            flags.append(f"lang:{patient.lang}")
    return Verification(verified=not removed and not flags, citations=kept, removed=removed, flags=flags,
                        bad_nodes=bad_h)


FALLBACK_HEAD = {"vi": "Việc diễn giải kết quả cần bác sĩ. Hồ sơ ghi:",
                 "en": "Interpreting these results needs a doctor. The record shows:"}
MAX_FALLBACK_LINES = 12


def values_answer(views: list[dict], lang: str) -> str:
    """route patient_info, after a failed regeneration: the values of the nodes read, listed by code (no model).
    Context nodes first (the question asked for history), newest first; every line cites its node."""
    lines = []
    context = sorted([v for v in views if v["node_id"].startswith(("results.", "encounters."))],
                     key=lambda v: v["node_id"].split(".")[-1], reverse=True)
    fixed = [v for v in views if v not in context]
    for v in context + fixed:
        ref = f"[H:{v['node_id']}]"
        facts = sorted(v.get("facts", []), key=lambda f: f.get("date") or f.get("month") or "", reverse=True)
        for f in facts:  # newest first within a node too ("the last tests")
            if "observations" in f:
                for o in f["observations"] or []:
                    unit = f" {o['unit']}" if o.get("unit") else ""
                    lines.append(f"- {o.get('display')}: {o.get('value')}{unit} ({o.get('date') or f.get('date')}) {ref}")
            elif "class" in f:
                lines.append(f"- {f['class'].replace('_', ' ')} ({f.get('month')}) {ref}")
            elif "value" in f:
                unit = f" {f['unit']}" if f.get("unit") else ""
                lines.append(f"- {f.get('display') or f.get('description')}: {f['value']}{unit} ({f.get('date')}) {ref}")
            elif f.get("substance") or f.get("display") or f.get("description"):  # narrative rows: description
                when = f" ({f['date']})" if f.get("description") and f.get("date") else ""
                lines.append(f"- {f.get('substance') or f.get('display') or f.get('description')}{when} {ref}")
    if not lines:
        return ("Hồ sơ không có thông tin cho câu hỏi này." if lang == "vi"
                else "The record holds no information for this question.")
    return "\n".join([FALLBACK_HEAD.get(lang, FALLBACK_HEAD["en"]), *lines[:MAX_FALLBACK_LINES]])


def text_of(answer: str, cards: list[RecipeCard]) -> str:
    """The answer with the cited Recipes' titles and the [R..] / R<id> marks masked (the text check runs on this)."""
    by_id = {r.id: r for r in cards}
    titles = [by_id[i].title for i in cited(answer) if i in by_id] + [r.title for r in cards
                                                                       if re.search(rf"(?<!\w)R{r.id}(?!\w)", answer)]
    return re.sub(r"\[R\d+\]|(?<!\w)R\d+(?!\w)", " ", mask(answer, titles))


def drop_sentences(answer: str, cards: list[RecipeCard], terms: dict[str, list[str]]) -> str:
    """Remove every sentence whose text (titles masked) suggests something the patient must avoid."""
    kept = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", answer):
        if part.strip() and not suggested_avoided(text_of(part, cards), terms):
            kept.append(part.strip())
    return " ".join(kept)


AVOID_HEAD = {"vi": "Theo hồ sơ, bệnh nhân cần tránh: {what}. Không thể gợi ý món có các thành phần này.",
              "en": "The patient's record says to avoid: {what}. Dishes with these cannot be suggested."}
LIST_HEAD = {"vi": "Các món phù hợp với ràng buộc của hồ sơ (vui lòng kiểm tra nhãn thành phần):",
             "en": "Dishes that keep the record's constraints (please check ingredient labels):"}
NONE_FOUND = {"vi": "Không tìm thấy món nào phù hợp với các ràng buộc này.",
              "en": "No dish fits these constraints."}


def recipes_answer(cards: list[RecipeCard], c: Constraints, lang: str, names: dict[str, str]) -> str:
    """route retrieve, when the answer still fails after regeneration and sentence dropping: the Recipes that keep
    the constraints, listed by code, with what must be avoided (no model)."""
    what = ", ".join([names.get(a, a.replace("_", " ")) for a in c.allergens_exclude]
                     + (["một số nguyên liệu khác" if lang == "vi" else "some other ingredients"]
                        if c.ingredients_exclude else []))
    ok = [r for r in cards if not violations(r, c)]
    lines = [AVOID_HEAD.get(lang, AVOID_HEAD["en"]).format(what=what)] if what else []
    if not ok:
        return "\n".join([*lines, NONE_FOUND.get(lang, NONE_FOUND["en"])])
    return "\n".join([*lines, LIST_HEAD.get(lang, LIST_HEAD["en"]), *(f"- [R{r.id}] {r.title}" for r in ok)])


def strip(answer: str, removed: list[int], bad_nodes: list[str] = ()) -> str:
    """Drop the bad citation marks; the text around them stays (the regenerated answer replaces it if needed)."""
    bad = set(removed)
    out = re.sub(r" ?\[R(\d+)\]", lambda m: "" if int(m.group(1)) in bad else m.group(0), answer)
    nodes = set(bad_nodes)
    return re.sub(r" ?\[H:([^\]\s]+)\]", lambda m: "" if m.group(1) in nodes else m.group(0), out) if nodes else out


def retry_note(v: Verification, cards: list[RecipeCard], c: Constraints) -> str:
    allowed = ", ".join(f"[R{r.id}]" for r in cards if not violations(r, c)) or "none (say nothing fits)"
    bad = ", ".join(f"[R{i}]" for i in v.removed)
    note = (f"Your previous answer failed the citation check: it cited {bad}, which are not allowed. "
            f"Rewrite it citing only: {allowed}.") if v.removed else "Rewrite your answer."
    if v.flags:  # patient checks (MV3)
        words = [f.split(":", 1)[1] for f in v.flags if f.startswith("text:")]
        nodes = [f.split(":", 1)[1] for f in v.flags if f.startswith("node:")]
        if words:
            note += f" Do not suggest anything the patient must avoid ({', '.join(words)})."
        if nodes:
            note += f" These record sections do not exist: {', '.join(nodes)}; cite only node ids from PATIENT_PROFILE."
        numbers = [f.split(":", 1)[1] for f in v.flags if f.startswith("number:")]
        words = [f.split(":", 1)[1] for f in v.flags if f.startswith("interpret:")]
        lang = [f.split(":", 1)[1] for f in v.flags if f.startswith("lang:")]
        if numbers or words or lang or "echo:prompt_block" in v.flags:  # route patient_info: values only
            note = ("Rewrite your previous answer as 2 to 4 short sentences in "
                    + ({"vi": "Vietnamese", "en": "English"}[lang[0]] if lang else "the same language as the question")
                    + ". "
                    + (f"Delete these numbers, which are not in RECORD: {', '.join(numbers)}. " if numbers else "")
                    + (f"Do not judge the values (no words like: {', '.join(words)}); say that interpreting them needs "
                       "a doctor. " if words else "")
                    + "Add no reference range and no number of your own. Do not copy RECORD or PATIENT_PROFILE, "
                    "and do not list the profile's limits or warnings.")
    return note
