"""The lexicon at query time, read from the tables scripts/tag.py writes (ingredient, ingredient_alias_vi,
allergen): the same canonical names the tags use, so a constraint M1 extracts can be filtered on.

Vietnamese aliases are looked up only on phrases M1 extracted as constraints, never by scanning the whole
message (short words such as "đường" or "giá" have other meanings), except `hints`, which only tells M1 that
an ambiguous word is present (resolve = context / ask, Thy's M1 decisions).
"""

import re
import unicodedata
from dataclasses import dataclass, field

import psycopg

from ..textmatch import key, longest_matches, unaccent, words
from .schemas import ALLERGENS


@dataclass(frozen=True)
class Alias:
    resolve: str  # fixed | all | context | ask
    ingredients: tuple[str, ...]  # canonical names
    allergens: tuple[str, ...]


@dataclass
class RuntimeLexicon:
    canonical: dict[str, str] = field(default_factory=dict)  # synonym key -> canonical
    aliases: dict[str, Alias] = field(default_factory=dict)  # normalized Vietnamese alias -> targets

    @classmethod
    def load(cls, conn: psycopg.Connection) -> "RuntimeLexicon":
        lex = cls()
        for name, syns in conn.execute("SELECT canonical_name, synonyms FROM ingredient"):
            for s in [name, *syns]:
                lex.canonical[key(s)] = name
        rows: dict[str, dict] = {}
        for alias, ing, code, resolve in conn.execute(
                "SELECT a.alias, i.canonical_name, a.allergen_code, a.resolve FROM ingredient_alias_vi a "
                "LEFT JOIN ingredient i ON i.id = a.ingredient_id"):
            r = rows.setdefault(norm(alias), {"resolve": resolve, "ing": [], "all": []})
            if ing:
                r["ing"].append(ing)
            if code:
                r["all"].append(code)
        lex.aliases = {a: Alias(r["resolve"], tuple(dict.fromkeys(r["ing"])), tuple(dict.fromkeys(r["all"])))
                       for a, r in rows.items()}
        return lex

    def to_canonical(self, name: str) -> list[str]:
        """Canonical ingredients named in an English phrase ("fresh cilantro leaves" -> cilantro)."""
        whole = self.canonical.get(key(name))
        if whole:
            return [whole]
        return list(dict.fromkeys(longest_matches(words(name), self.canonical)))

    def vi(self, phrase: str) -> Alias | None:
        """A Vietnamese constraint phrase -> its alias entry (accented first, then unaccented)."""
        p = norm(phrase)
        return self.aliases.get(p) or self.aliases.get(unaccent(p))

    def hints(self, message: str) -> list[tuple[str, Alias]]:
        """Ambiguous aliases (context / ask) present in the message as whole words."""
        text = norm(message)
        found = []
        for alias, a in self.aliases.items():
            if a.resolve in {"context", "ask"} and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
                found.append((alias, a))
        return found


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).lower()).strip()


def valid_allergens(codes: list[str]) -> list[str]:
    return [c for c in ALLERGENS if c in set(codes)]
