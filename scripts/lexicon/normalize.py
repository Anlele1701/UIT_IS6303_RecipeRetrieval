"""D5: map a parsed ingredient name to canonical ingredients from data/lexicon/ingredients.csv.

Matching scans the name left to right and takes the longest synonym that starts at each word,
so one line can yield several ingredients ("salt and ground black pepper" -> salt, black pepper),
and a longer synonym beats the words inside it ("cream of tartar" is not "cream", "coconut milk"
is not "milk"). Words that start no synonym are skipped. A name with no match is `unknown` (D8).
Synonyms and names go through the same `key()`, so plural/singular and hyphens never matter.
"""

import csv
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from .parse import DESCRIPTORS, SIZES

LEXICON = Path(__file__).resolve().parents[2] / "data" / "lexicon"
# The word rules and the scan live in api/textmatch.py, shared with the online pipeline.
from api.textmatch import MAX_WORDS, key, longest_matches, singular, words  # noqa: E402,F401


def core(name: str) -> str:
    """The name without descriptor and size words, singular: the bootstrap's candidate canonical."""
    return " ".join(w for w in words(name) if w not in DESCRIPTORS and w not in SIZES)


@dataclass
class Lexicon:
    canonical: dict[str, str] = field(default_factory=dict)  # synonym key -> canonical
    groups: dict[str, str] = field(default_factory=dict)  # canonical -> group

    @classmethod
    def from_csv(cls, path: Path = LEXICON / "ingredients.csv") -> "Lexicon":
        lex = cls()
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lex.groups[row["canonical"]] = row["group"]
                for s in [row["canonical"], *filter(None, row["synonyms"].split("|"))]:
                    lex.canonical[key(s)] = row["canonical"]
        return lex

    def match(self, name: str) -> list[str]:
        """Canonical ingredients in a parsed name, in order, without repeats."""
        return list(dict.fromkeys(longest_matches(words(name), self.canonical)))


@cache
def default_lexicon() -> Lexicon:
    return Lexicon.from_csv()
