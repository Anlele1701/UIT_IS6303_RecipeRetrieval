import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import report_numbers as rn  # noqa: E402

DATA = {"m6": {"summary": {"S|t2": {"cvr_adj": {"mean": 0.0267}, "safe_adj": {"k": 14, "n": 15}}},
               "comparisons": {"cvr_adj": {"S - B0": {"diff": -0.6018, "p": 0.0004}}}},
        "c": {"D1": {"recipes": 32719}}}


def test_a_placeholder_walks_bracketed_keys_and_formats_the_vietnamese_way():
    out, missing = rn.render("CVR {{m6:summary.[S|t2].cvr_adj.mean|pct}}, Safe {{m6:summary.[S|t2].safe_adj|kn}}, "
                             "Δ {{m6:comparisons.cvr_adj.[S - B0].diff|sf3}}, p {{m6:comparisons.cvr_adj.[S - B0].p|p}}, "
                             "{{c:D1.recipes|int}} công thức", DATA)
    assert missing == []
    assert out == "CVR 2,7%, Safe 14/15, Δ −0,602, p < 0,001, 32.719 công thức"


def test_an_unknown_key_or_a_malformed_placeholder_is_reported_never_left_silently():
    out, missing = rn.render("{{m6:summary.[S|t9].cvr_adj.mean|pct}} and {{m6 broken}}", DATA)
    assert len(missing) == 2 and "THIẾU" in out
    assert rn.fmt([-0.749, -0.451], "ci") == "[−0,75; −0,45]" and rn.fmt(10889.7, "int") == "10.890"


def test_the_report_sources_fill_completely():
    data = {k: __import__("json").loads(p.read_text(encoding="utf-8")) for k, p in rn.SOURCES.items() if p.exists()}
    data["d"] = rn.derived()
    for src in sorted(rn.SRC.glob("*.md")):
        _, missing = rn.render(src.read_text(encoding="utf-8"), data)
        assert missing == [], (src.name, missing[:3])
