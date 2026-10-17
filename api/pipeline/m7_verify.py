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
    (at the precision written), so the answer cannot invent or derive a measurement; and the answer must not copy
    the data blocks (RECORD, PATIENT_PROFILE) back.
Without a patient context, verify() is exactly the M3 check.
"""

import re
from dataclasses import dataclass, field

from ..patient.nutrition import meets
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


@dataclass
class PatientCheck:
    node_ids: set[str]  # every node of the patient's tree: [H:..] must name one
    avoid_terms: dict[str, list[str]] = field(default_factory=dict)  # constraint -> words that name it
    numbers: set[float] | None = None  # route patient_info: every number the answer may state (facts read)


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


def unknown_numbers(answer: str, allowed: set[float]) -> list[str]:
    """Numbers in the answer that match no allowed value, at the precision the answer writes them
    ("67.7" matches 67.68). Citation marks and list numbering are not numbers of the record."""
    text = LIST_MARK.sub(" ", re.sub(r"\[(?:R\d+|H:[^\]]+)\]", " ", answer))
    bad = []
    for token in NUMBER.findall(text):
        x = float(token.replace(",", "."))
        decimals = len(re.split(r"[.,]", token)[1]) if re.search(r"[.,]", token) else 0
        tol = 0.5 * 10 ** -decimals + 1e-9
        if not any(abs(a - x) <= tol for a in allowed):
            bad.append(token)
    return list(dict.fromkeys(bad))


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
    flags = [f"text:{k}" for k in suggested_avoided(answer, patient.avoid_terms)] + [f"node:{h}" for h in bad_h]
    if patient.numbers is not None:  # route patient_info: every number must come from a fact read (Thy, after MV3)
        flags += [f"number:{n}" for n in unknown_numbers(answer, patient.numbers)]
        if ECHO.search(answer):  # the data blocks copied back instead of an answer
            flags.append("echo:prompt_block")
    return Verification(verified=not removed and not flags, citations=kept, removed=removed, flags=flags,
                        bad_nodes=bad_h)


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
        if numbers or "echo:prompt_block" in v.flags:  # route patient_info: keep the answer, drop what is not in RECORD
            note = ("Rewrite your previous answer as 2 to 4 short sentences in the same language. "
                    + (f"Delete these numbers, which are not in RECORD: {', '.join(numbers)}. " if numbers else "")
                    + "Add no reference range and no number of your own. Do not copy RECORD or PATIENT_PROFILE, "
                    "and do not list the profile's limits or warnings.")
    return note
