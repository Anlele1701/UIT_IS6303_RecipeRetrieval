"""M5 V6 helper (Thy chose it, 19/10/2026): a DRAFT of the gold review for Thy to confirm, never the review itself.

    uv run scripts/draft_testset_review.py      # -> eval/labels/testset_review_draft.csv (reviewer: claude-draft)

- A template item keeps the gold its template wrote (decision ok).
- A handwritten item, or an A1 query flagged `needs_gold`, gets the gold below, written from Thy's notes in
  eval/testset/handwritten.csv (decision edit).
- An item is `flagged` for Thy to look at first: handwritten, needs_gold, a paraphrased T2 query (the guard may
  miss a drift in meaning), a V3 warning, or a draft that the schema cannot express in full (see the note).
scripts/testset_review.py shows the draft and lets Thy accept, fix or drop; only Thy's rows reach the freeze
(eval/labels/testset_review.csv, reviewer Thy). The draft file is never read by scripts/freeze_testset.py.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import testset_review as tr  # noqa: E402

DRAFT = ROOT / "eval" / "labels" / "testset_review_draft.csv"
FIELDS = ["item_id", "decision", "gold", "note", "flagged", "flag_reason", "reviewer", "drafted_at"]


def g(intent="search", allergens=(), ingredients=(), diet=None, minutes=None) -> dict:
    return {"intent": intent, "constraints": {"allergens_exclude": list(allergens), "ingredients_exclude": list(ingredients),
                                              "diet": diet, "max_total_minutes": minutes}}


# item -> (gold, note). Notes say where the schema falls short; Thy decides.
DRAFTS = {
    "t1_013": (g(), "no-bake không phải ràng buộc; peanut butter là nguyên liệu muốn có, không phải loại trừ"),
    "t1_062": (g(), "không ràng buộc"),
    "t1_073": (g(), "không ràng buộc"),
    "t1_101": (g(), ""), "t1_102": (g(), ""), "t1_103": (g(), ""), "t1_104": (g(), ""), "t1_105": (g(), ""),
    "t2_151": (g(allergens=["peanut"]), "lạc = đậu phộng; ràng buộc cho con của người hỏi"),
    "t2_152": (g(allergens=["fish", "crustacean_shellfish"]), "hải sản: cá và giáp xác; nhuyễn thể không có nhóm riêng trong 9 nhóm FDA"),
    "t2_153": (g(allergens=["egg"]), ""),
    "t2_154": (g(diet="vegetarian", minutes=20), ""),
    "t2_155": (g(diet="vegan"), "giàu đạm: sở thích mềm, schema không biểu diễn"),
    "t2_156": (g(allergens=["wheat"]), "gluten → wheat; lúa mạch, lúa mạch đen ngoài 9 nhóm (hạn chế)"),
    "t2_157": (g(ingredients=["onion"]), "không phải dị ứng"),
    "t2_158": (g(allergens=["milk"]), "bơ = butter, thuộc nhóm sữa"),
    "t2_159": (g(), "bơ = avocado; không ràng buộc"),
    "t2_160": (g(allergens=["crustacean_shellfish"]), "tôm cũng là giáp xác; ràng buộc vẫn áp cho cả nhóm"),
    "t2_161": (g(), "thích tôm: không phải ràng buộc"),
    "t2_162": (g(), "dị ứng trứng đã khỏi: không ràng buộc"),
    "t2_163": (g(allergens=["sesame", "soy"]), ""),
    "t2_164": (g(), "đồ sống: schema không biểu diễn; để trống, kỳ vọng hệ nêu rõ không kiểm được"),
    "t2_165": (g(allergens=["wheat"], minutes=10), "không có bột mì → wheat"),
    "t2_166": (g(allergens=["tree_nuts"]), "nuts → tree_nuts; Thy cân nhắc thêm peanut"),
    "t2_167": (g(ingredients=["cilantro"]), "khẩu phần 4 người không lọc"),
    "t2_168": (g(diet="vegetarian"), "ăn trứng sữa → vegetarian, không phải vegan"),
    "t2_169": (g(allergens=["tree_nuts"]), "'hạt' mơ hồ; Thy cân nhắc thêm peanut (mè, hạt chia cũng là hạt)"),
    "t2_170": (g(ingredients=["onion", "garlic"]), "không cay: sở thích mềm; không suy ra bệnh"),
    "t2_171": (g(allergens=["peanut"]), ""),
    "t2_172": (g(allergens=["milk", "egg"]), "bơ sữa = butter và sữa"),
    "t3_051": (g(intent="out_of_scope"), "hỏi thuốc: từ chối, khuyên hỏi bác sĩ"),
    "t3_052": (g(), "món có thể không có trong kho: tìm và trả lời không thấy"),
    "t3_053": (g(allergens=["egg", "milk", "wheat", "tree_nuts"], minutes=5),
               "không bột → wheat; không hạt → tree_nuts (Thy cân nhắc peanut); không đường: schema không biểu diễn"),
    "t3_054": (g(intent="out_of_scope"), ""),
    "t3_055": (g(intent="out_of_scope"), "chèn lệnh: từ chối"),
}
SCHEMA_GAPS = {"t2_155", "t2_156", "t2_164", "t2_166", "t2_169", "t3_053"}


def flag_reason(it: dict) -> str:
    reasons = []
    if it.get("source") == "handwritten":
        reasons.append("viết tay")
    elif it.get("needs_gold"):
        reasons.append("T1 có từ giống ràng buộc")
    if it.get("paraphrased"):
        reasons.append("đã diễn đạt lại")
    if it.get("v3_warning"):
        reasons.append("cảnh báo V3")
    if it["id"] in SCHEMA_GAPS:
        reasons.append("schema không biểu diễn đủ")
    return ", ".join(reasons)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    items = tr.items()
    missing = [it["id"] for it in items if it.get("needs_gold") and it["id"] not in DRAFTS]
    if missing:
        sys.exit(f"no draft for: {', '.join(missing)}")
    now = datetime.now().isoformat(timespec="seconds")
    with open(DRAFT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for it in items:
            reason = flag_reason(it)
            if it["id"] in DRAFTS:
                gold, note = DRAFTS[it["id"]]
                w.writerow({"item_id": it["id"], "decision": "edit", "gold": json.dumps(gold, ensure_ascii=False),
                            "note": note, "flagged": bool(reason), "flag_reason": reason, "reviewer": "claude-draft",
                            "drafted_at": now})
            else:
                w.writerow({"item_id": it["id"], "decision": "ok", "gold": "", "note": "", "flagged": bool(reason),
                            "flag_reason": reason, "reviewer": "claude-draft", "drafted_at": now})
    flagged = sum(bool(flag_reason(it)) for it in items)
    print(f"{len(items)} drafted, {flagged} flagged for Thy -> {DRAFT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
