"""
Constructed query + ground-truth set. See docs/03_DATASET.md §3.5.

The dataset (ANDREEEWW/recipe-with-images) has no native retrieval ground
truth, so the query/relevance set here is built by the project team and
saved to a versioned file so every configuration in docs/10_ABLATION_STUDY.md
is evaluated against the identical set.

Queries are split into four families so that per-family metrics can show
*where* a method wins, not just that it wins on average:

    name_kw          recipe title with stopwords/serial numbers removed
    ingredient_combo the most discriminative ingredient terms of a recipe
    desc_short       the description, truncated and stripped of title words
    synonym_hard     ingredient_combo with ingredients swapped for synonyms
                     that do not occur in the source recipe

Every query is derived from a document that is itself in the corpus, so a
lexical bias remains in the first three families; `synonym_hard` exists to
measure that bias rather than hide it. This must be disclosed in the report.
"""

import argparse
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.config import CONFIG
from src.db import connect

# US -> UK/alternative naming. Applied to whole words inside an ingredient
# term; a substitution only counts if the replacement is absent from the
# source recipe's own text (see _gen_synonym_hard).
INGREDIENT_SYNONYMS = {
    # Produce
    "cilantro": "coriander",
    "eggplant": "aubergine",
    "eggplants": "aubergines",
    "zucchini": "courgette",
    "zucchinis": "courgettes",
    "arugula": "rocket",
    "beets": "beetroot",
    "beet": "beetroot",
    "romaine": "cos",
    "rutabaga": "swede",
    "endive": "chicory",
    "snow": "mangetout",   # "snow peas"
    "fava": "broad",       # "fava beans"
    "navy": "haricot",     # "navy beans"
    "scallions": "spring onions",
    "scallion": "spring onion",
    "chickpeas": "garbanzo beans",
    "chickpea": "garbanzo bean",
    "garbanzo": "chickpea",
    # Protein
    "shrimp": "prawns",
    "shrimps": "prawns",
    "hamburger": "minced beef",
    "ground": "minced",    # "ground beef", "lean ground beef"
    # Dairy
    "heavy": "double",     # "heavy cream", "heavy whipping cream"
    "half-and-half": "single cream",
    "skim": "skimmed",
    # Store cupboard
    "cornstarch": "cornflour",
    "cornmeal": "polenta",
    "molasses": "treacle",
    "raisins": "sultanas",
    "raisin": "sultana",
    "peanuts": "groundnuts",
    "oatmeal": "porridge",
    "canola": "rapeseed",
    "confectioners": "icing",
    "confectioners'": "icing",
    "powdered": "icing",
    "all-purpose": "plain",
    "wheat": "wholemeal",
    "semisweet": "plain",  # "semisweet chocolate chips"
    "broth": "stock",
    "bouillon": "stock",
    "paste": "puree",      # "tomato paste"
    "catsup": "ketchup",
    "ketchup": "tomato ketchup",
    "jello": "jelly",
    "jelly": "jam",
    # Baked goods
    "graham": "digestive",
    "cracker": "biscuit",
    "crackers": "biscuits",
    "cookies": "biscuits",
    "cookie": "biscuit",
    "biscuit": "scone",
    "candy": "sweets",
    "popsicle": "ice lolly",
    "cupcake": "fairy cake",
}

# A query is only accepted into synonym_hard once this many of its terms have
# been rewritten. One swap out of four leaves three exact-matching terms, which
# a lexical retriever still resolves trivially.
_MIN_SUBSTITUTIONS = 2

# Measurement words stripped from the head of an ingredient line.
_UNIT_WORDS = {
    "tablespoon", "tablespoons", "tbsp", "tbs", "teaspoon", "teaspoons", "tsp",
    "cup", "cups", "ounce", "ounces", "oz", "pound", "pounds", "lb", "lbs",
    "gram", "grams", "kilogram", "kilograms", "milliliter", "milliliters",
    "millilitre", "millilitres", "liter", "liters", "litre", "litres",
    "pint", "pints", "quart", "quarts", "gallon", "gallons", "clove", "cloves",
    "can", "cans", "package", "packages", "packet", "packets", "pkg",
    "container", "containers", "jar", "jars", "bottle", "bottles",
    "bunch", "bunches", "slice", "slices", "piece", "pieces", "pinch",
    "pinches", "dash", "dashes", "sprig", "sprigs", "stalk", "stalks",
    "head", "heads", "sheet", "sheets", "stick", "sticks", "envelope",
    "envelopes", "box", "boxes", "bag", "bags", "inch", "inches", "cm",
    "tin", "tins", "recipe", "batch", "serving", "servings", "portion",
    # Metric abbreviations survive as bare letters once the digits of
    # "300g/10oz" are dropped by the word regex.
    "g", "kg", "mg", "ml", "l", "cl", "dl", "fl",
}

# Preparation / size adjectives stripped from the head of an ingredient line.
_PREP_WORDS = {
    "large", "medium", "small", "whole", "fresh", "freshly", "dried", "dry",
    "frozen", "chopped", "minced", "sliced", "diced", "grated", "shredded",
    "ground", "melted", "softened", "packed", "peeled", "cooked", "uncooked",
    "beaten", "crushed", "cubed", "halved", "quartered", "drained", "rinsed",
    "optional", "plus", "more", "about", "approximately", "finely", "thinly",
    "coarsely", "roughly", "lightly", "well", "very", "extra", "and", "or",
    "of", "to", "taste", "a", "an", "the", "such", "as", "needed", "each",
    "warm", "cold", "hot", "room", "temperature", "all-purpose", "allpurpose",
    "boneless", "skinless", "unsalted", "salted", "low-fat", "nonfat",
    "reduced-fat", "prepared", "divided", "firmly", "heaping", "level",
    "ripe", "raw", "toasted", "roasted", "canned", "bottled", "instant",
    "new", "old", "good", "quality", "any", "your", "favorite", "favourite",
}

# Corpus-wide pantry staples are dropped from ingredient queries: they carry
# almost no retrieval signal. Terms above _STAPLE_DF_RATIO are dropped too;
# this list only covers head-noun forms that survive normalization.
_STAPLE_WORDS = {
    "salt", "pepper", "water", "sugar", "butter", "oil", "flour", "egg",
    "milk", "vanilla", "extract", "garlic", "onion", "black", "white",
    "brown", "olive", "vegetable", "baking", "powder", "soda", "and", "or",
}

_TITLE_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "with", "without", "for", "in", "on",
    "to", "from", "by", "my", "our", "your", "best", "easy", "quick", "simple",
    "perfect", "ultimate", "homemade", "classic", "favorite", "favourite",
    "style", "recipe", "recipes", "make", "made", "super", "real", "authentic",
}

_ROMAN_NUMERAL = re.compile(r"^(?=[ivxlcdm]+$)m*(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")
_FRACTION_CHARS = "".join(
    chr(code) for code in range(0x2150, 0x215F)
) + "\u00bc\u00bd\u00be"
_WORD = re.compile(r"[a-z][a-z'\-]*")

# Selection parameters for ingredient-based queries.
_STAPLE_DF_RATIO = 0.10  # terms in >10% of recipes are not discriminative
_MIN_TERM_DF = 2         # terms unique to one recipe make the task trivial
_INGREDIENTS_PER_QUERY = 4
_DESC_MAX_WORDS = 12
_DESC_MIN_WORDS = 4
_NEAR_DUPLICATE_JACCARD = 0.8


@dataclass
class EvalQuery:
    query_id: int
    family: str
    query_text: str
    source_recipe_idx: int          # recipe the query was derived from
    relevant_recipe_ids: list[int]  # includes source_recipe_idx at minimum
    # Pre-substitution text for `synonym_hard`; empty for other families.
    # Recorded for error analysis, never evaluated on its own.
    base_query_text: str = ""
    substitutions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorpusRecipe:
    recipe_idx: int
    name: str
    ingredients: str
    description: str


def load_corpus_from_db() -> list[CorpusRecipe]:
    """
    Read the indexed corpus straight from `raw.recipes` rather than
    re-deriving it from Hugging Face, so the query set is guaranteed to be
    built against exactly the documents that are searchable.
    """
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT recipe_idx, name, ingredients, description
            FROM raw.recipes
            ORDER BY recipe_idx
            """
        ).fetchall()
    return [CorpusRecipe(int(r[0]), r[1] or "", r[2] or "", r[3] or "") for r in rows]


def _strip_accents_fractions(text: str) -> str:
    return "".join(ch for ch in text if ch not in _FRACTION_CHARS)


def _singularize(word: str) -> str:
    if len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes"):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def normalize_term(term: str) -> str:
    """Key used for document-frequency counting and Jaccard overlap."""
    return " ".join(_singularize(w) for w in term.split())


def extract_ingredient_terms(raw: str) -> list[str]:
    """
    Reduce a raw recipe-style ingredient block to a list of head terms.

    "2 cloves garlic, crushed"                -> "garlic"
    "1 (2 inch) piece fresh ginger, peeled"   -> "ginger"
    "300g/10oz sweet shortcrust pastry"       -> "sweet shortcrust pastry"

    Sub-headers ("Dressing:", "For serving:") and quantity/unit/prep tokens
    are dropped. Order is preserved and duplicates removed.
    """
    if not raw:
        return []

    terms: list[str] = []
    seen: set[str] = set()
    for line in raw.replace("\xa0", " ").split("\n"):
        line = unicodedata.normalize("NFKD", line)
        line = re.sub(r"\([^)]*\)", " ", line)  # "(2 inch)", "(optional)"
        line = line.split(",")[0]               # drop prep clause after comma
        line = line.lower().strip()
        if not line or line.endswith(":"):
            continue

        words = [
            word.strip("'-")
            for word in _WORD.findall(_strip_accents_fractions(line))
        ]
        words = [word for word in words if word]
        # Leading quantity/unit/prep tokens carry no retrieval signal.
        start = 0
        while start < len(words) and (
            words[start] in _UNIT_WORDS or words[start] in _PREP_WORDS
        ):
            start += 1
        term = " ".join(words[start:]).strip()

        # Trailing prep words ("chicken wings split" keeps wings; "sugar to
        # taste" drops the tail).
        parts = term.split()
        while parts and parts[-1] in _PREP_WORDS:
            parts.pop()
        term = " ".join(parts)

        if not term or len(term) < 3 or len(parts) > 5:
            continue
        key = normalize_term(term)
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms


def _document_frequency(term_lists: list[list[str]]) -> Counter:
    df: Counter = Counter()
    for terms in term_lists:
        df.update({normalize_term(t) for t in terms})
    return df


def _clean_description(raw: str) -> str:
    text = raw.strip()
    # Descriptions are frequently stored wrapped in literal quote characters.
    text = text.strip('"').strip("'").strip()
    return re.sub(r"\s+", " ", text)


def _title_keywords(name: str) -> list[str]:
    name = re.sub(r"\([^)]*\)", " ", name)
    words = _WORD.findall(name.lower())
    kept = [
        w
        for w in words
        if w not in _TITLE_STOPWORDS and not _ROMAN_NUMERAL.match(w) and len(w) > 1
    ]
    return kept


# --------------------------------------------------------------------------
# Query generators. Each returns (query_text, base_text, substitutions) or
# None when the recipe cannot produce a usable query of that family.
# --------------------------------------------------------------------------


def _gen_name_kw(recipe: CorpusRecipe, terms: list[str], df: Counter, total: int):
    kept = _title_keywords(recipe.name)
    if len(kept) < 2:
        return None
    return " ".join(kept), "", []


def _select_ingredients(terms: list[str], df: Counter, total: int) -> list[str]:
    """Most discriminative ingredients: rare enough to identify, not unique."""
    staple_cutoff = total * _STAPLE_DF_RATIO
    scored = []
    for term in terms:
        key = normalize_term(term)
        freq = df.get(key, 0)
        # A term made up entirely of pantry and preparation words ("salt and
        # freshly ground pepper") adds noise even when its surface form is rare.
        if all(word in _STAPLE_WORDS or word in _PREP_WORDS for word in key.split()):
            continue
        if freq > staple_cutoff or freq < _MIN_TERM_DF:
            continue
        scored.append((freq, term))
    # Ascending DF: rarest (most identifying) first, ties broken on the term
    # itself so the selection is deterministic.
    scored.sort(key=lambda pair: (pair[0], pair[1]))
    return [term for _, term in scored[:_INGREDIENTS_PER_QUERY]]


def _gen_ingredient_combo(recipe: CorpusRecipe, terms: list[str], df: Counter, total: int):
    chosen = _select_ingredients(terms, df, total)
    if len(chosen) < 3:
        return None
    return ", ".join(chosen), "", []


def _gen_desc_short(recipe: CorpusRecipe, terms: list[str], df: Counter, total: int):
    description = _clean_description(recipe.description)
    if not description:
        return None
    title_words = {_singularize(w) for w in _title_keywords(recipe.name)}
    words = _WORD.findall(description.lower())
    # Removing title words is what keeps this family from being a verbatim
    # copy of the indexed document.
    kept = [w for w in words if _singularize(w) not in title_words]
    kept = kept[:_DESC_MAX_WORDS]
    while kept and kept[-1] in _TITLE_STOPWORDS:
        kept.pop()
    if len(kept) < _DESC_MIN_WORDS:
        return None
    return " ".join(kept), "", []


def _gen_synonym_hard(recipe: CorpusRecipe, terms: list[str], df: Counter, total: int):
    chosen = _select_ingredients(terms, df, total)
    if len(chosen) < 3:
        return None

    document = f"{recipe.name} {recipe.ingredients} {recipe.description}".lower()
    swapped: list[str] = []
    substitutions: list[str] = []
    for term in chosen:
        words = term.split()
        new_words = []
        for word in words:
            replacement = INGREDIENT_SYNONYMS.get(word)
            # Only a replacement absent from the source document makes the
            # query genuinely hard for a lexical matcher.
            if replacement and not re.search(rf"\b{re.escape(replacement.split()[0])}", document):
                new_words.append(replacement)
                substitutions.append(f"{word} -> {replacement}")
            else:
                new_words.append(word)
        swapped.append(" ".join(new_words))

    if len(substitutions) < _MIN_SUBSTITUTIONS:
        return None
    return ", ".join(swapped), ", ".join(chosen), substitutions


_GENERATORS = {
    "name_kw": _gen_name_kw,
    "ingredient_combo": _gen_ingredient_combo,
    "desc_short": _gen_desc_short,
    "synonym_hard": _gen_synonym_hard,
}


def _near_duplicates(
    source_idx: int,
    term_keys: list[set[str]],
    idx_by_position: list[int],
    position_of: dict[int, int],
) -> list[int]:
    """
    Recipes whose ingredient sets overlap the source above
    _NEAR_DUPLICATE_JACCARD are treated as also-relevant, so a duplicated
    dish in the corpus is not scored as a retrieval error.
    """
    source_terms = term_keys[position_of[source_idx]]
    if len(source_terms) < 3:
        return []
    extra = []
    for position, other_terms in enumerate(term_keys):
        other_idx = idx_by_position[position]
        if other_idx == source_idx or len(other_terms) < 3:
            continue
        intersection = len(source_terms & other_terms)
        if not intersection:
            continue
        union = len(source_terms | other_terms)
        if intersection / union >= _NEAR_DUPLICATE_JACCARD:
            extra.append(other_idx)
    return extra


def build_query_set(
    corpus: list[CorpusRecipe],
    per_family: int = 75,
    seed: int = 42,
) -> list[EvalQuery]:
    """
    Build a deterministic query set with `per_family` queries per family.

    Source recipes are sampled disjointly across families so no recipe
    contributes two queries, keeping per-family metrics independent.
    """
    rng = random.Random(seed)
    term_lists = [extract_ingredient_terms(r.ingredients) for r in corpus]
    df = _document_frequency(term_lists)
    total = len(corpus)

    term_keys = [{normalize_term(t) for t in terms} for terms in term_lists]
    idx_by_position = [r.recipe_idx for r in corpus]
    position_of = {r.recipe_idx: i for i, r in enumerate(corpus)}

    used: set[int] = set()
    queries: list[EvalQuery] = []
    query_id = 0

    for family, generator in _GENERATORS.items():
        order = list(range(len(corpus)))
        rng.shuffle(order)
        taken = 0
        for position in order:
            if taken >= per_family:
                break
            recipe = corpus[position]
            if recipe.recipe_idx in used:
                continue
            produced = generator(recipe, term_lists[position], df, total)
            if produced is None:
                continue
            query_text, base_text, substitutions = produced

            relevant = [recipe.recipe_idx] + _near_duplicates(
                recipe.recipe_idx, term_keys, idx_by_position, position_of
            )
            queries.append(
                EvalQuery(
                    query_id=query_id,
                    family=family,
                    query_text=query_text,
                    source_recipe_idx=recipe.recipe_idx,
                    relevant_recipe_ids=relevant,
                    base_query_text=base_text,
                    substitutions=substitutions,
                )
            )
            used.add(recipe.recipe_idx)
            query_id += 1
            taken += 1

        if taken < per_family:
            print(
                f"warning: family {family!r} produced only {taken}/{per_family} queries",
                file=sys.stderr,
            )

    return queries


def _query_set_hash(queries: list[EvalQuery]) -> str:
    payload = json.dumps([asdict(q) for q in queries], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def save_query_set(queries: list[EvalQuery], path: str, per_family: int, seed: int) -> None:
    document = {
        "metadata": {
            "dataset_name": CONFIG.dataset_name,
            "dataset_revision": CONFIG.dataset_revision,
            "corpus_split": CONFIG.corpus_split,
            "subset_size": CONFIG.subset_size,
            "subset_seed": CONFIG.seed,
            "query_seed": seed,
            "per_family": per_family,
            "families": list(_GENERATORS),
            "num_queries": len(queries),
            "near_duplicate_jaccard": _NEAR_DUPLICATE_JACCARD,
            "query_set_hash": _query_set_hash(queries),
        },
        "queries": [asdict(q) for q in queries],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)


def load_query_set(path: str) -> tuple[list[EvalQuery], dict]:
    with open(path, "r", encoding="utf-8") as f:
        document = json.load(f)
    queries = [EvalQuery(**item) for item in document["queries"]]
    return queries, document.get("metadata", {})


def load_queries(path: str) -> list[EvalQuery]:
    return load_query_set(path)[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the constructed evaluation query set")
    parser.add_argument("--out", default=f"{CONFIG.experiments_dir}/queries_v1.json")
    parser.add_argument("--per-family", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    corpus = load_corpus_from_db()
    queries = build_query_set(corpus, per_family=args.per_family, seed=args.seed)
    save_query_set(queries, args.out, per_family=args.per_family, seed=args.seed)

    by_family = Counter(q.family for q in queries)
    multi_gold = sum(1 for q in queries if len(q.relevant_recipe_ids) > 1)
    print(f"Wrote {len(queries)} queries to {args.out}")
    for family, count in by_family.items():
        print(f"  {family:<18} {count}")
    print(f"  queries with >1 relevant recipe: {multi_gold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
