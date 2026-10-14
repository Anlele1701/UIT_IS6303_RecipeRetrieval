"""M7 citation check (sườn báo cáo 3.4): every [R<id>] must be a context Recipe that keeps the definite constraints.

A citation outside the context, or to a Recipe whose definite tags break an allergen, ingredient or diet
constraint, is removed. Possible tags never count as a break (they are warnings, Thy M1). When any citation was
removed, or the context had Recipes but the answer cites none, the orchestrator regenerates once.
"""

import re

from .schemas import Constraints, RecipeCard, Verification

CITE = re.compile(r"\[R(\d+)\]")


def violations(card: RecipeCard, c: Constraints) -> list[str]:
    out = [f"allergen:{a}" for a in c.allergens_exclude if a in card.allergens]
    out += [f"ingredient:{i}" for i in c.ingredients_exclude if i in card.ingredients_norm]
    if c.diet and c.diet not in card.diet_flags:
        out.append(f"diet:{c.diet}")
    return out


def cited(answer: str) -> list[int]:
    return list(dict.fromkeys(int(m) for m in CITE.findall(answer)))


def verify(answer: str, cards: list[RecipeCard], c: Constraints) -> Verification:
    by_id = {r.id: r for r in cards}
    ids = cited(answer)
    removed = [i for i in ids if i not in by_id or violations(by_id[i], c)]
    kept = [i for i in ids if i not in removed]
    return Verification(verified=not removed and (bool(kept) or not cards), citations=kept, removed=removed)


def strip(answer: str, removed: list[int]) -> str:
    """Drop the bad citation marks; the text around them stays (the regenerated answer replaces it if needed)."""
    bad = set(removed)
    return re.sub(r" ?\[R(\d+)\]", lambda m: "" if int(m.group(1)) in bad else m.group(0), answer)


def retry_note(v: Verification, cards: list[RecipeCard], c: Constraints) -> str:
    allowed = ", ".join(f"[R{r.id}]" for r in cards if not violations(r, c)) or "none (say nothing fits)"
    why = f"It cited {', '.join(f'[R{i}]' for i in v.removed)}, which are not allowed. " if v.removed else \
        "It cited no recipe. "
    return f"Your previous answer failed the citation check. {why}Rewrite it citing only: {allowed}."
