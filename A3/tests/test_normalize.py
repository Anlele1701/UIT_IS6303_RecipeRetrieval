"""D5: singular forms, cores and the longest-match scan, on a small hand-made lexicon and the real one."""

import pytest

from lexicon.normalize import Lexicon, core, default_lexicon, key, singular


@pytest.mark.parametrize("plural,single", [
    ("tomatoes", "tomato"), ("berries", "berry"), ("leaves", "leaf"), ("cookies", "cookie"),
    ("peaches", "peach"), ("olives", "olive"), ("molasses", "molasses"), ("hummus", "hummus"),
    ("bananas", "banana"), ("chilies", "chili"), ("oats", "oat"), ("egg", "egg"),
])
def test_singular(plural, single):
    assert singular(plural) == single


def test_key_ignores_case_hyphens_and_plurals():
    assert key("Half-and-Half") == key("half and half")
    assert key("Sun-Dried Tomatoes") == "sun dried tomato"


def test_core_drops_descriptor_and_size_words():
    assert core("finely chopped fresh parsley") == "parsley"
    assert core("large eggs") == "egg"
    assert core("skinless boneless chicken breast halves") == "chicken breast"


def small() -> Lexicon:
    lex = Lexicon()
    for canonical, syns, group in [
        ("salt", [], ""), ("black pepper", ["pepper"], ""), ("butter", [], "dairy"),
        ("margarine", [], ""), ("cream", [], "dairy"), ("cream of tartar", [], ""),
        ("coconut milk", [], ""), ("milk", [], "dairy"), ("tomato sauce", [], ""),
    ]:
        lex.groups[canonical] = group
        for s in [canonical, *syns]:
            lex.canonical[key(s)] = canonical
    return lex


@pytest.mark.parametrize("name,expected", [
    ("salt and ground black pepper", ["salt", "black pepper"]),
    ("salt and pepper", ["salt", "black pepper"]),
    ("butter or margarine", ["butter", "margarine"]),  # every alternative counts (conservative)
    ("cream of tartar", ["cream of tartar"]),  # longest match beats "cream"
    ("light coconut milk", ["coconut milk"]),  # not "milk"
    ("contadina tomato sauce", ["tomato sauce"]),  # brand word skipped
    ("frobnicated widgets", []),  # unknown (D8)
])
def test_match(name, expected):
    assert small().match(name) == expected


def test_real_lexicon_maps_the_most_common_names():
    lex = default_lexicon()
    assert lex.match("all-purpose flour") == ["all purpose flour"]
    assert lex.match("powdered sugar") == ["confectioners sugar"]
    assert lex.match("garbanzo beans") == ["chickpea"]
    assert lex.match("salt and freshly ground black pepper") == ["salt", "black pepper"]
