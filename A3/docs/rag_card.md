# RAG Card – A3

Sinh tự động bởi `scripts/make_cards.py`. Không sửa tay. Theo đề xuất RAG Card của Faridi và cộng sự [9]: mô tả snapshot dữ liệu, cách chia chunk, mô hình, prompt và tham số để tái lập kết quả.

## 1. Snapshot dữ liệu

- Kho công thức: Shengtao/recipe (`data/recipe.csv`), 32.722 dòng → 32.719 công thức sau D1. Pipeline dữ liệu chạy lúc 2026-10-17T21:33:04, commit `f2f8100`, seed 42.
- Từ điển và luật (sha256, 12 ký tự đầu): `allergens.csv` 67a09676858f, `rules.csv` 4f363b653a67, `manual_synonyms.csv` 5b0f4ee9a001, `ingredients.csv` c2a3a49041f0, `allergen_map.csv` c9e52ffd0db8, `vi_alias.csv` d197420ab448.
- Hồ sơ bệnh nhân: tài liệu C-CDA R2.1 sinh bằng Synthea (xem Data Card, mục 2).
- Bộ test A3 đóng băng: sha256 ghi trong `eval/testset/frozen.json`; bộ câu hỏi hồ sơ: `eval/patient/frozen.json`.

## 2. Chunk và chỉ mục

- Chiến lược chunk dùng cho chat: `semantic` (kế thừa A1; bảng `chunk` phân vùng theo chiến lược, ADR 0002). Kết quả được gom về cấp công thức ở M5.
- BM25 (ParadeDB `pg_search`) và dense (`nomic-embed-text`, chỉ mục vector trong ParadeDB, ADR 0003), mỗi nhánh lấy 50 chunk, hợp nhất RRF.
- Xếp hạng lại: `mixedbread-ai/mxbai-rerank-base-v1` trên 50 ứng viên; xếp hạng tới độ sâu 10, đưa 5 công thức đầu vào ngữ cảnh.

## 3. Mô hình và tham số sinh

| Vai trò | Mô hình | Tham số |
|---|---|---|
| Hiểu truy vấn (M1), chọn nút (V2), tóm tắt nút (V1) | `qwen2.5:7b` | temperature 0.0, seed 42, num_ctx 4096 (V2 8192, V1 16384), structured output (JSON schema) |
| Sinh câu trả lời (M6) | `qwen2.5:7b` | temperature 0.2, seed 42, num_ctx 8192, tối đa 2048 token |
| Embedding | `nomic-embed-text` | – |
| Xếp hạng lại (M5) | `mixedbread-ai/mxbai-rerank-base-v1` | 50 ứng viên |
| Bộ kiểm độc lập (đánh giá) | `llama3.1:8b` | temperature 0, tối đa 1024 token; không dùng từ điển hay thẻ của bộ gắn thẻ |
| Judge (đánh giá) | `llama3.1:8b` | temperature 0, num_ctx 8192, tối đa 512 token |

Mọi lời gọi LLM được lưu đệm theo hash của (mô hình, schema, prompt, temperature, seed) trong `data/cache/llm.jsonl`. Prompt bị cắt bởi Ollama được chặn bằng `check_fits` và `check_not_cut` (`api/pipeline/llm.py`).

## 4. Cấu hình so sánh (cờ trong `api/pipeline/flags.py`)

| Preset | qu | conv | filter | norm | rerank | generate | verify |
|---|---|---|---|---|---|---|---|
| B0 | – | – | – | – | ✓ | – | – |
| B1 | – | – | – | – | ✓ | ✓ | – |
| S | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| S-QU | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| S-Filter | ✓ | ✓ | – | ✓ | ✓ | ✓ | ✓ |
| S-Norm | ✓ | ✓ | ✓ | – | ✓ | ✓ | ✓ |
| S-Conv | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| S-Rerank | ✓ | ✓ | ✓ | ✓ | – | ✓ | ✓ |
| S-Verify | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – |

Nhánh hồ sơ: `P-Direct` (đọc trường có mã), `P-Vectorless` (= S: nút cố định đọc bằng code + V2 chọn nút), `P-Vectorless-Fixed` (không có nút cố định, V2 chọn mọi nút), `P-Vector` (RAG vector trên chính hồ sơ), `S-Profile` (bỏ ràng buộc hồ sơ).

## 5. Prompt

Nguyên văn ở các file dưới đây; hash đổi khi chữ đổi.

| Prompt | File | sha256 (12) |
|---|---|---|
| M1 SYSTEM | `api/pipeline/m1_understand.py` | 3884fb4aee2e |
| M1 SYSTEM_PATIENT | `api/pipeline/m1_understand.py` | 428f33d52215 |
| M6 RULES | `api/pipeline/m6_generate.py` | d3a66b65dbec |
| M6 DETAIL | `api/pipeline/m6_generate.py` | e57c88f4a81f |
| M6 CHAT | `api/pipeline/m6_generate.py` | 1bbd1e3c1b63 |
| M6 PATIENT_RULES | `api/pipeline/m6_generate.py` | 73dc8bbbb715 |
| M6 PATIENT_INFO | `api/pipeline/m6_generate.py` | 15d51183db07 |
| V1 tóm tắt nút | `api/patient/summarize.py` | a029a0c6b939 |
| V2 chọn nút | `api/patient/navigate.py` | dc260f433a86 |
| P-Vector trích ràng buộc | `api/patient/baselines.py` | a5834dced16a |
| Bộ kiểm độc lập | `scripts/checker.py` | 0e668387a2c0 |
| Judge độ liên quan | `scripts/judge.py` | fa054d0b1beb |
| Judge faithfulness | `scripts/judge.py` | 310a8e6d298c |
| Judge trả lời đúng câu hỏi | `scripts/judge.py` | 62321373f081 |
| Judge từ chối | `scripts/judge.py` | 800bf01b867b |

## 6. Lần chạy đánh giá

| Lần chạy | Thư mục | Bắt đầu | Commit | Seed | Máy |
|---|---|---|---|---|---|
| M6 (bộ test A3) | `eval/runs/20261019-093605/a3` | 2026-10-19T09:36:05 | b7daea9 | 42 | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |
| MV4 (nhánh hồ sơ) | `eval/runs/20261018-132948/patient` | 2026-10-18T13:29:48 | b0fd1da | 42 | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |

M6 chạy trên mẫu theo seed khoảng 10% bộ test: T1 10, T2 17, T3 6, T4 4 (danh sách câu trong `settings.json`).
