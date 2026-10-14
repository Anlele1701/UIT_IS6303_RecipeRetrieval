"""Word normalization and longest-phrase matching, shared by the offline tagger (scripts/lexicon) and the
online pipeline (api/pipeline), so a name maps to the same canonical ingredient in both."""

import re
import unicodedata
from typing import TypeVar

MAX_WORDS = 6
KEEP_S = {"molasses", "hummus", "asparagus", "couscous", "swiss", "grits", "schnapps", "bitters", "brussels",
          "lemongrass", "watercress", "citrus", "octopus", "anise"}
IRREGULAR = {"leaves": "leaf", "halves": "half", "loaves": "loaf", "cookies": "cookie", "brownies": "brownie",
             "chilies": "chili", "chillies": "chili", "veggies": "veggie", "pierogies": "pierogi",
             "smoothies": "smoothie", "knives": "knife"}
T = TypeVar("T")


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


def longest_matches(ws: list[str], table: dict[str, T]) -> list[T]:
    """Scan left to right; at each word take the longest phrase in `table` that starts there.
    A longer phrase wins over the words inside it; words that start no phrase are skipped."""
    out, i = [], 0
    while i < len(ws):
        for n in range(min(MAX_WORDS, len(ws) - i), 0, -1):
            hit = table.get(" ".join(ws[i:i + n]))
            if hit is not None:
                out.append(hit)
                i += n
                break
        else:
            i += 1
    return out


def unaccent(s: str) -> str:
    """Vietnamese without diacritics ("đậu phộng" -> "dau phong"), for users who type without them."""
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


VI_MARKS = re.compile(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", re.I)
VI_WORDS = {"khong", "toi", "minh", "mon", "an", "gi", "nao", "cho", "voi", "duoc", "nhung", "lam", "di", "ung",
            "co", "la", "va", "cua", "nau", "phut", "duoi", "chay", "thu", "the", "muon", "hay"}


def looks_vietnamese(text: str) -> bool:
    """Diacritics, or several common Vietnamese words typed without them."""
    if VI_MARKS.search(text):
        return True
    toks = re.findall(r"[a-z]+", unaccent(text).lower())
    return sum(t in VI_WORDS for t in toks) >= 2
