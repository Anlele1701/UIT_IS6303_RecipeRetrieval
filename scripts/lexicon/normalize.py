"""D5: map a parsed ingredient name to canonical ingredients from data/lexicon/ingredients.csv.

Matching scans the name left to right and takes the longest synonym that starts at each word,
so one line can yield several ingredients ("salt and ground black pepper" -> salt, black pepper),
and a longer synonym beats the words inside it ("cream of tartar" is not "cream", "coconut milk"
is not "milk"). Words that start no synonym are skipped. A name with no match is `unknown` (D8).
Synonyms and names go through the same `key()`, so plural/singular and hyphens never matter.
"""

import csv
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from .parse import DESCRIPTORS, SIZES

LEXICON = Path(__file__).resolve().parents[2] / "data" / "lexicon"
MAX_WORDS = 6
KEEP_S = {"molasses", "hummus", "asparagus", "couscous", "swiss", "grits", "schnapps", "bitters", "brussels",
          "lemongrass", "watercress", "citrus", "octopus", "anise"}
IRREGULAR = {"leaves": "leaf", "halves": "half", "loaves": "loaf", "cookies": "cookie", "brownies": "brownie",
             "chilies": "chili", "chillies": "chili", "veggies": "veggie", "pierogies": "pierogi",
             "smoothies": "smoothie", "knives": "knife"}


def singular(w: str) -> str:
    if w in IRREGULAR:
        return IRREGULAR[w]
    if len(w) <= 3 or w in KEEP_S or w.endswith(("ss", "us", "is")):
        return w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith(("ches", "shes", "xes", "zes")):
        return w[:-2]
    if w.endswith("s"):
        return w[:-1]
    return w


def words(text: str) -> list[str]:
    text = re.sub(r"[-/]", " ", text.lower().replace("'", ""))
    return [singular(w) for w in re.findall(r"[a-z0-9&]+", text)]


def key(text: str) -> str:
    return " ".join(words(text))


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
        ws, out, i = words(name), [], 0
        while i < len(ws):
            for n in range(min(MAX_WORDS, len(ws) - i), 0, -1):
                c = self.canonical.get(" ".join(ws[i:i + n]))
                if c:
                    if c not in out:
                        out.append(c)
                    i += n
                    break
            else:
                i += 1
        return out


@cache
def default_lexicon() -> Lexicon:
    return Lexicon.from_csv()
