# CLAUDE.md – Đồ án A3 (IS6303, UIT)

## Bối cảnh
- A3 phát triển A1 (hệ truy hồi công thức: BM25 + dense + RRF + rerank trên ParadeDB) thành **trợ lý RAG hội thoại nhận biết ràng buộc**: dị ứng, loại trừ nguyên liệu, chế độ ăn, thời gian. Người dùng nhập tiếng Việt hoặc tiếng Anh, LLM chạy cục bộ qua Ollama.
- Kế hoạch build: `docs/plan/A3_ke_hoach_build.md` (**nguồn sự thật cho thứ tự việc, đặc tả và gate**).
- Thiết kế và lý thuyết: `docs/plan/A3_suon_bao_cao.md`. Tài liệu tham khảo: `docs/plan/A3_tong_hop_tai_lieu.md` (PDF không có trong repo).
- Bàn giao và cách dựng lại môi trường: `docs/handoff.md`.
- Code A1 (chỉ đọc): `../A1/UIT_IS6303_RecipeRetrieval/tony/`. Thuật ngữ trong `CONTEXT.md` của A1 vẫn dùng: Recipe, Chunk, Chunking strategy, Fusion baseline, Answer key, Evaluation run, Ablation run…
- Repo này chính là code của A3 (trên máy gốc nằm ở `A3/recipe-assistant/`).

## Quy tắc bắt buộc
1. **Không sửa, xóa hay commit gì trong thư mục `A1/`.** Chỉ được copy code từ đó sang.
2. **Không đụng Docker volume của A1** (`is603_recipe-pgdata`). A3 dùng compose project và volume riêng.
3. **Hỏi trước mọi thao tác khó đảo ngược:** xóa dữ liệu hoặc volume, `DROP`, reset git, ghi đè file nhãn trong `eval/labels/` và `eval/testset/`.
4. **Bắt đầu mỗi mốc bằng plan mode** và trình kế hoạch. Dừng ở mỗi 🚦 gate để Thy duyệt. Không tự làm sang mốc sau.
5. **Không gán nhãn thay người.** Các việc 👤 trong kế hoạch là của Thy. Chỉ xây công cụ và dừng chờ.
6. **Gán nhãn phải mù:** công cụ gán nhãn không hiển thị dự đoán của bộ gắn thẻ hay của bộ kiểm.
7. **Bộ kiểm độc lập** (`scripts/checker.py`) **không được import** lexicon, thẻ hay bất kỳ code nào của bộ gắn thẻ. Có test kiểm tra điều này.
8. Bộ test sau gate M5 là **đóng băng**: không sửa `eval/testset/*.jsonl`.
9. **Mọi bước lọc hoặc làm sạch dữ liệu phải có mã quy tắc (D-x, V-x) và số đếm** được ghi tự động vào JSON. Không gõ số tay vào báo cáo.
10. **Mọi nhánh ablation chạy cùng một code**, chỉ khác cờ trong `api/pipeline/flags.py`.

## Quy ước kỹ thuật
- Python ≥ 3.11, quản lý bằng `uv`. FastAPI, psycopg 3. Test bằng `pytest`.
- UI: React + Vite + Tailwind, kế thừa `ui/` của A1.
- Mô hình mặc định:
  - Embedding: `nomic-embed-text`.
  - Reranker: `mixedbread-ai/mxbai-rerank-base-v1`.
  - Hiểu truy vấn và sinh câu trả lời: `qwen2.5:7b`.
  - Judge và bộ kiểm độc lập: `llama3.1:8b`.

  Tất cả lấy từ biến môi trường, có giá trị mặc định trong `api/config.py`.
- Gọi LLM: dùng structured output của Ollama (`format` = JSON schema), cache theo hash của đầu vào, seed cố định.
- Seed cố định cho mọi bước lấy mẫu. Ghi seed vào `settings.json` của từng run.
- Commit nhỏ theo từng việc, message dạng `feat|fix|eval|docs: …`.
- Sau mỗi gate, cập nhật `docs/progress.md` (ngày, mốc, số liệu chính, quyết định).
- Code và comment viết tiếng Anh. Tài liệu `docs/` và nội dung trình cho Thy viết tiếng Việt.
