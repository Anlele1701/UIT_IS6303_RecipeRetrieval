"""RAG Card and Data Card (build plan M7; Faridi et al. 2026, sườn báo cáo 2.4 and Phụ lục).

    uv run scripts/make_cards.py      # writes docs/rag_card.md and docs/data_card.md

Every number comes from a file the pipeline wrote (CLAUDE.md rule 9): eval/corpus.json (D-x),
eval/patient_corpus.json (P-x), eval/testset/testset_flow.json (V-x), eval/patient/queries_summary.json, the
settings and metrics of the M6 and MV4 runs. Models, parameters and prompts are read from the code itself.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

M6_RUN = ROOT / "eval" / "runs" / "20261019-093605" / "a3"
MV4_RUN = ROOT / "eval" / "runs" / "20261018-132948" / "patient"
DOCS = ROOT / "docs"
RULE_VI = {"D1": "Loại dòng trùng URL với một dòng trước đó", "D2": "Bỏ cột dinh dưỡng rỗng trên 99%",
           "D3": "Đổi thời gian (\"1 hr 10 mins\") ra phút; null khi rỗng hoặc không đọc được",
           "D4": "Tách dòng nguyên liệu thành số lượng, đơn vị, tên, ghi chú (theo luật)",
           "D5": "Ánh xạ tên về nguyên liệu chuẩn (từ đồng nghĩa dài nhất trước)",
           "D6": "Gắn 9 nhóm dị ứng FDA cho nguyên liệu chuẩn: chắc chắn (trực tiếp hoặc ẩn) thì lọc, có thể (tùy nhãn hiệu) "
                 "thì chỉ cảnh báo",
           "D6b": "Dòng ghi rõ không chứa X (gluten-free, dairy-free, vegan…) không mang nhóm X",
           "D7": "Chay: không có nhóm động vật, cá, giáp xác; thuần chay: thêm không sữa, trứng, mật ong",
           "D8": "Dòng không ánh xạ được là unknown; mặc định không đổi thẻ"}
SETS_VI = {"t1": "T1 hồi quy (từ bộ truy vấn A1)", "t2": "T2 ràng buộc một lượt", "t3": "T3 không trả lời được",
           "t4": "T4 hội thoại nhiều lượt"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def num(x) -> str:
    """Vietnamese thousands separator (32.719) and decimal comma (0,99)."""
    if isinstance(x, float):
        return f"{x:.4g}".replace(".", ",")
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else str(x)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%".replace(".", ",")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def prompts() -> list[tuple[str, str, str]]:
    """(where, name, text) of every prompt the system and the evaluation send to a model."""
    from api.patient import baselines, navigate, summarize
    from api.pipeline import m1_understand, m6_generate
    import checker
    import judge
    return [("api/pipeline/m1_understand.py", "M1 SYSTEM", m1_understand.SYSTEM),
            ("api/pipeline/m1_understand.py", "M1 SYSTEM_PATIENT", m1_understand.SYSTEM_PATIENT),
            ("api/pipeline/m6_generate.py", "M6 RULES", m6_generate.RULES),
            ("api/pipeline/m6_generate.py", "M6 DETAIL", m6_generate.DETAIL),
            ("api/pipeline/m6_generate.py", "M6 CHAT", m6_generate.CHAT),
            ("api/pipeline/m6_generate.py", "M6 PATIENT_RULES", m6_generate.PATIENT_RULES),
            ("api/pipeline/m6_generate.py", "M6 PATIENT_INFO", m6_generate.PATIENT_INFO),
            ("api/patient/summarize.py", "V1 tóm tắt nút", summarize.SYSTEM),
            ("api/patient/navigate.py", "V2 chọn nút", navigate.SYSTEM),
            ("api/patient/baselines.py", "P-Vector trích ràng buộc", baselines.SYSTEM),
            ("scripts/checker.py", "Bộ kiểm độc lập", checker.PROMPT),
            ("scripts/judge.py", "Judge độ liên quan", judge.REL),
            ("scripts/judge.py", "Judge faithfulness", judge.FAITH),
            ("scripts/judge.py", "Judge trả lời đúng câu hỏi", judge.ANSWERS),
            ("scripts/judge.py", "Judge từ chối", judge.REFUSES)]


def rag_card() -> str:
    from api import config
    from api.pipeline import llm, orchestrator
    from api.pipeline.flags import PRESETS
    from api.pipeline import m4_retrieve
    import checker
    import judge
    corpus = load(ROOT / "eval" / "corpus.json")
    s6 = load(M6_RUN / "settings.json")
    s4 = load(MV4_RUN / "settings.json")
    flags = ["qu", "conv", "filter", "norm", "rerank", "generate", "verify"]
    preset_rows = [[name] + ["✓" if getattr(f, k) else "–" for k in flags]
                   for name, f in PRESETS.items() if name in {"B0", "B1", "S", "S-QU", "S-Filter", "S-Norm", "S-Conv",
                                                               "S-Rerank", "S-Verify"}]
    lines = [
        "# RAG Card – A3",
        "",
        "Sinh tự động bởi `scripts/make_cards.py`. Không sửa tay. Theo đề xuất RAG Card của Faridi và cộng sự [9]: "
        "mô tả snapshot dữ liệu, cách chia chunk, mô hình, prompt và tham số để tái lập kết quả.",
        "",
        "## 1. Snapshot dữ liệu",
        "",
        f"- Kho công thức: Shengtao/recipe (`data/recipe.csv`), {num(corpus['D1']['csv_rows'])} dòng → "
        f"{num(corpus['D1']['recipes'])} công thức sau D1. Pipeline dữ liệu chạy lúc {corpus['ran_at']}, "
        f"commit `{corpus['git_commit']}`, seed {corpus['seed']}.",
        "- Từ điển và luật (sha256, 12 ký tự đầu): "
        + ", ".join(f"`{k}` {v[:12]}" for k, v in corpus["lexicon_sha256"].items()) + ".",
        "- Hồ sơ bệnh nhân: tài liệu C-CDA R2.1 sinh bằng Synthea (xem Data Card, mục 2).",
        f"- Bộ test A3 đóng băng: sha256 ghi trong `eval/testset/frozen.json`; bộ câu hỏi hồ sơ: "
        f"`eval/patient/frozen.json`.",
        "",
        "## 2. Chunk và chỉ mục",
        "",
        f"- Chiến lược chunk dùng cho chat: `{config.CHAT_STRATEGY}` (kế thừa A1; bảng `chunk` phân vùng theo chiến lược, "
        "ADR 0002). Kết quả được gom về cấp công thức ở M5.",
        f"- BM25 (ParadeDB `pg_search`) và dense (`{config.EMBED_MODEL}`, chỉ mục vector trong ParadeDB, ADR 0003), "
        f"mỗi nhánh lấy {m4_retrieve.POOL} chunk, hợp nhất RRF.",
        f"- Xếp hạng lại: `{config.RERANK_MODEL}` trên {config.RERANK_TOP} ứng viên; xếp hạng tới độ sâu "
        f"{orchestrator.RANK_DEPTH}, đưa 5 công thức đầu vào ngữ cảnh.",
        "",
        "## 3. Mô hình và tham số sinh",
        "",
        table(["Vai trò", "Mô hình", "Tham số"], [
            ["Hiểu truy vấn (M1), chọn nút (V2), tóm tắt nút (V1)", f"`{config.QU_MODEL}`",
             f"temperature {config.QU_TEMPERATURE}, seed {config.SEED}, num_ctx {llm.NUM_CTX} (V2 8192, V1 16384), "
             "structured output (JSON schema)"],
            ["Sinh câu trả lời (M6)", f"`{config.GEN_MODEL}`",
             f"temperature {config.GEN_TEMPERATURE}, seed {config.SEED}, num_ctx {llm.GEN_CTX}, "
             f"tối đa {llm.GEN_MAX_TOKENS} token"],
            ["Embedding", f"`{config.EMBED_MODEL}`", "–"],
            ["Xếp hạng lại (M5)", f"`{config.RERANK_MODEL}`", f"{config.RERANK_TOP} ứng viên"],
            ["Bộ kiểm độc lập (đánh giá)", f"`{checker.CHECKER_MODEL}`",
             f"temperature 0, tối đa {checker.MAX_TOKENS} token; không dùng từ điển hay thẻ của bộ gắn thẻ"],
            ["Judge (đánh giá)", f"`{judge.JUDGE_MODEL}`",
             f"temperature 0, num_ctx {judge.JUDGE_CTX}, tối đa {judge.JUDGE_MAX_TOKENS} token"],
        ]),
        "",
        "Mọi lời gọi LLM được lưu đệm theo hash của (mô hình, schema, prompt, temperature, seed) trong "
        "`data/cache/llm.jsonl`. Prompt bị cắt bởi Ollama được chặn bằng `check_fits` và `check_not_cut` "
        "(`api/pipeline/llm.py`).",
        "",
        "## 4. Cấu hình so sánh (cờ trong `api/pipeline/flags.py`)",
        "",
        table(["Preset"] + flags, preset_rows),
        "",
        "Nhánh hồ sơ: `P-Direct` (đọc trường có mã), `P-Vectorless` (= S: nút cố định đọc bằng code + V2 chọn nút), "
        "`P-Vectorless-Fixed` (không có nút cố định, V2 chọn mọi nút), `P-Vector` (RAG vector trên chính hồ sơ), "
        "`S-Profile` (bỏ ràng buộc hồ sơ).",
        "",
        "## 5. Prompt",
        "",
        "Nguyên văn ở các file dưới đây; hash đổi khi chữ đổi.",
        "",
        table(["Prompt", "File", "sha256 (12)"], [[n, f"`{w}`", sha(t)] for w, n, t in prompts()]),
        "",
        "## 6. Lần chạy đánh giá",
        "",
        table(["Lần chạy", "Thư mục", "Bắt đầu", "Commit", "Seed", "Máy"], [
            ["M6 (bộ test A3)", f"`{M6_RUN.relative_to(ROOT).as_posix()}`", s6["started"], s6["git"][:7],
             s6["seed"], s6["machine"]["gpu"]],
            ["MV4 (nhánh hồ sơ)", f"`{MV4_RUN.relative_to(ROOT).as_posix()}`", s4.get("started", "–"),
             str(s4.get("git", "–"))[:7], s4.get("seed", "–"), (s4.get("machine") or {}).get("gpu", "–")],
        ]),
        "",
        "M6 chạy trên mẫu theo seed khoảng 10% bộ test: "
        + ", ".join(f"{k.upper()} {len(v)}" for k, v in s6["qids"].items())
        + " (danh sách câu trong `settings.json`).",
        "",
    ]
    return "\n".join(lines)


def data_card() -> str:
    c = load(ROOT / "eval" / "corpus.json")
    p = load(ROOT / "eval" / "patient_corpus.json")
    flow = load(ROOT / "eval" / "testset" / "testset_flow.json")
    pq = load(ROOT / "eval" / "patient" / "queries_summary.json")
    d6 = c["D6"]["per_allergen"]
    d_rows = [
        ["D1", RULE_VI["D1"], f"{num(c['D1']['duplicate_urls_dropped'])} dòng trùng URL bị loại; còn "
                                f"{num(c['D1']['recipes'])} công thức"],
        ["D2", RULE_VI["D2"], f"{num(c['D2']['columns_dropped'])} cột bị bỏ"],
        ["D3", RULE_VI["D3"], "; ".join(f"{k}: {num(v['null'])} null" for k, v in c["D3"]["per_column"].items())],
        ["D4", RULE_VI["D4"], f"{num(c['D4']['lines'])} dòng; ok {pct(c['D4']['status_share']['ok'])}, partial "
                                f"{pct(c['D4']['status_share']['partial'])}, fail {num(c['D4']['status']['fail'])}"],
        ["D5", RULE_VI["D5"], f"{num(c['D5']['canonicals'])} nguyên liệu chuẩn; độ phủ dòng "
                                f"{pct(c['D5']['coverage'])}"],
        ["D6", RULE_VI["D6"], "; ".join(f"{k} {num(v['recipes'])}" for k, v in d6.items())],
        ["D6b", RULE_VI["D6b"], f"{num(c['D6b']['lines'])} dòng ở {num(c['D6b']['recipes'])} công thức"],
        ["D7", RULE_VI["D7"], f"chay {num(c['D7']['vegetarian'])} ({pct(c['D7']['vegetarian_share'])}), thuần chay "
                                f"{num(c['D7']['vegan'])} ({pct(c['D7']['vegan_share'])})"],
        ["D8", RULE_VI["D8"], f"{num(c['D8']['unknown_lines'])} dòng unknown ở {num(c['D8']['recipes_with_unknown'])}"
                                f" công thức ({pct(c['D8']['recipes_with_unknown_share'])})"],
    ]
    t = p["total"]
    v_rows = []
    for k, s in flow["sets"].items():
        rej = s["rejected"]
        v_rows.append([SETS_VI[k], s["generated"], *[rej[v] for v in ("V1", "V2", "V3", "V4", "V5")], s["kept"],
                       s["trimmed_to_target"], s["V6"]["final"]])
    v6 = flow["V6_review"]
    lines = [
        "# Data Card – A3",
        "",
        "Sinh tự động bởi `scripts/make_cards.py`. Không sửa tay. Mọi số đếm lấy từ JSON do pipeline ghi.",
        "",
        "## 1. Kho công thức (quy tắc D-x, `eval/corpus.json`)",
        "",
        f"Nguồn: Shengtao/recipe, công thức nấu ăn của Mỹ bằng tiếng Anh. Chạy lúc {c['ran_at']}, commit "
        f"`{c['git_commit']}`, {num(c['seconds'])} giây.",
        "",
        table(["Mã", "Quy tắc", "Số đếm"], d_rows),
        "",
        "Dị ứng theo 9 nhóm FDA; thẻ \"chắc chắn\" (trực tiếp hoặc thành phần ẩn) được lọc, thẻ \"có thể\" (phụ thuộc "
        "nhãn hiệu) chỉ được cảnh báo. Thông tin dị ứng suy ra từ nguyên liệu, không phản ánh nhiễm chéo.",
        "",
        "## 2. Hồ sơ bệnh nhân (quy tắc P-x, `eval/patient_corpus.json`)",
        "",
        f"Nguồn: tài liệu C-CDA R2.1 sinh bằng Synthea: "
        + "; ".join(f"`{s}`" for s in p["sources"]) + ". Dữ liệu tổng hợp, không có bệnh án thật.",
        "",
        table(["Mã", "Quy tắc", "Số đếm"], [
            ["P1", "Nạp mọi tài liệu C-CDA", f"{num(t['P1']['files'])} file, parse được {num(t['P1']['parsed'])}; "
                                              f"còn sống {num(t['P1']['alive'])}, đã mất {num(t['P1']['deceased'])}"],
            ["P2", "Chỉ giữ dị ứng và vấn đề đang hiệu lực", f"dị ứng giữ {num(t['P2']['allergies_in_force'])}; vấn đề "
                                                              f"bỏ {num(t['P2']['problems_dropped_not_in_force'])}"],
            ["P3", "Dị ứng thực phẩm (SNOMED 414285001), ánh xạ về 9 nhóm", f"{num(t['P3']['food_allergies'])} mục"],
            ["P4", "Vấn đề: chỉ giữ loại (disorder)", f"giữ {num(t['P4']['disorders_kept'])}; bỏ (finding) "
                                                      f"{num(t['P4']['dropped_suffix_finding'])}, (situation) "
                                                      f"{num(t['P4']['dropped_suffix_situation'])}"],
            ["P5", "Thuốc đang dùng", f"{num(t['P5']['in_use'])} đang dùng; {num(t['P5']['dropped_not_in_use'])} đã ngừng"],
            ["P6", "Sinh hiệu gần nhất, xét nghiệm, lần khám", f"{num(t['P6']['vitals_latest'])} chỉ số sinh hiệu; "
                                                                f"{num(t['P6']['result_organizers'])} nhóm xét nghiệm; "
                                                                f"{num(t['P6']['encounters'])} lần khám"],
            ["P7", "Không đưa vào ngữ cảnh mô hình: sức khỏe tâm thần, chất gây nghiện, bạo lực, định danh",
             f"{num(t['P7']['organizer_mental_health'])} nhóm sàng lọc tâm thần; "
             f"{num(t['P7']['organizer_substance_use'])} nhóm chất gây nghiện; "
             f"{num(t['P7']['organizer_violence'])} nhóm bạo lực; trường định danh không đọc ở "
             f"{num(t['P7']['identity_fields_not_read'])} hồ sơ"],
        ]),
        "",
        f"P8 (chọn bệnh nhân phân tầng) và báo cáo đầy đủ: `docs/patient_corpus_report.md`.",
        "",
        "## 3. Bộ test A3 (quy tắc V-x, `eval/testset/testset_flow.json`)",
        "",
        f"Sinh lúc {flow['generated_at']}, seed {flow['seed']}; diễn đạt lại bằng `{flow['paraphrase_model']}` "
        f"(khác họ với mô hình hiểu truy vấn); bộ kiểm V2 `{flow['checker_model']}`.",
        "",
        table(["Tập", "Sinh ra", "V1", "V2", "V3", "V4", "V5", "Còn lại", "Bớt khi cắt về chỉ tiêu", "Sau V6"], v_rows),
        "",
        f"- Câu viết tay của nhóm: {flow['handwritten']['rows']} câu, giữ {flow['handwritten']['kept']} "
        f"({flow['handwritten']['v3_warnings']} cảnh báo V3: không dấu hoặc trộn ngôn ngữ, vẫn giữ).",
        f"- V6 (xác nhận gold): {v6['draft']}. Xác nhận từng câu {v6['confirmed_one_by_one']} câu trong "
        f"{v6['one_by_one_seconds']} giây; chấp nhận hàng loạt {v6['bulk_accepted']} câu; bản nháp bị sửa "
        f"{v6['drafts_changed_by_thy']}.",
        f"- Đóng băng lúc {flow['frozen_at']}.",
        "",
        "## 4. Bộ câu hỏi hồ sơ bệnh nhân (`eval/patient/queries_summary.json`)",
        "",
        f"- {pq['patients']} bệnh nhân, {pq['questions']} câu: "
        + ", ".join(f"{k} {v}" for k, v in pq["by_type"].items())
        + f"; tiếng Việt {pq['by_lang']['vi']}, tiếng Anh {pq['by_lang']['en']}.",
        f"- V7: tập ràng buộc gold = ràng buộc lấy từ trường có mã của Synthea ∪ ràng buộc trong câu; ít nhất "
        f"{num(pq['v7_min_recipes'])} công thức thỏa ở câu chặt nhất.",
        f"- Kiểm tay bước lấy đáp án: {pq['manual_check_patients']} bệnh nhân (`eval/patient/manual_check.csv`).",
        "",
        "## 5. Nhãn",
        "",
        "- 200 công thức có nhãn dị ứng và chế độ ăn là **nhãn bạc** (Claude Sonnet gán mù theo hướng dẫn của nhóm; "
        "`eval/labels/report_allergen.md`), không có nhãn vàng do người gán.",
        "- Hàng duyệt mù của bộ kiểm (`eval/labels/checker_adjudication.csv`): người gán là Thy.",
        "- Kiểm của người M6 (`eval/labels/human_check.csv`): 160 mục, người gán là Thy.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    (DOCS / "rag_card.md").write_text(rag_card(), encoding="utf-8")
    (DOCS / "data_card.md").write_text(data_card(), encoding="utf-8")
    print("-> docs/rag_card.md, docs/data_card.md")
