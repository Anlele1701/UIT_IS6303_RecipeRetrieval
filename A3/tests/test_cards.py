import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import make_cards  # noqa: E402


def test_the_cards_build_from_the_recorded_files_only():
    rag, data = make_cards.rag_card(), make_cards.data_card()
    for text in (rag, data):
        assert "None" not in text and "{" not in text.replace("{lang}", "")  # every value was filled
    assert "D6b" in data and "P7" in data and "V6" in data and "nhãn bạc" in data
    assert all(name in rag for name in ("B0", "S-Verify", "qwen2.5:7b", "llama3.1:8b", "Bộ kiểm độc lập"))
    assert make_cards.num(32719) == "32.719" and make_cards.pct(0.9928) == "99,3%"
