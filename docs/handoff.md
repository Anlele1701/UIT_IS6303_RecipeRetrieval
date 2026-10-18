# Bàn giao A3 (15/10/2026)

Tài liệu này dành cho người làm tiếp A3 trên một máy khác. Nó cho biết dự án đang ở đâu, cách dựng lại môi trường, và việc tiếp theo cần làm. Chi tiết số liệu và quyết định của từng gate nằm ở `docs/progress.md`.

## 1. Trạng thái

| Mốc | Trạng thái |
|---|---|
| M0: dựng nền, tái lập A1 | 🚦 đã duyệt (14/10) |
| M1: từ điển nguyên liệu, gắn thẻ D1–D8 | 🚦 đã duyệt (14/10) |
| M2: mẫu kiểm 200 công thức, nhãn bạc, bộ kiểm độc lập | 🚦 đã duyệt (15/10) |
| M3: pipeline hội thoại M1–M7 | **code xong, chưa qua gate** |
| M4 trở đi (API `/chat`, UI, bộ test, đánh giá) | chưa bắt đầu |

**Việc đầu tiên cần làm:** gate M3. Chạy `scripts/chat_cli.py`, thử khoảng 20 câu tự nghĩ (tiếng Việt và tiếng Anh, có câu nhiều lượt, có câu gỡ ràng buộc), ghi lỗi, rồi duyệt. Kết quả 4 kịch bản demo nằm ở `eval/m3_demo.json`. Sau gate M3, cập nhật `docs/progress.md` rồi mới sang M4.

## 2. Tài liệu cần đọc

- `CLAUDE.md` (gốc repo): các quy tắc bắt buộc. Quan trọng nhất là: không gán nhãn thay người, bộ kiểm không được import code của bộ gắn thẻ, bộ test bị đóng băng sau gate M5, mọi nhánh ablation chạy chung một code.
- `docs/plan/A3_ke_hoach_build.md`: **nguồn sự thật** cho thứ tự việc, đặc tả và gate.
- `docs/plan/A3_suon_bao_cao.md`: thiết kế và lý thuyết. `docs/plan/A3_tong_hop_tai_lieu.md`: tài liệu tham khảo. Các file PDF không đưa lên repo.
- `docs/progress.md`: nhật ký các gate.
- `CONTEXT.md`: thuật ngữ, kế thừa từ A1.

## 3. Dựng lại môi trường

### Cần có
- Docker Desktop.
- `uv`: Python 3.12 được ghim trong `pyproject.toml` và `uv.lock`.
- Ollama, với các model:
  ```
  ollama pull nomic-embed-text
  ollama pull qwen2.5:7b
  ollama pull llama3.1:8b
  ```
- Node 20 trở lên, chỉ cần từ M4 cho UI.

### Cơ sở dữ liệu
DB của A3 đã chứa thẻ dị ứng, cờ chế độ ăn và các bảng chat (migration 001–005). Bản dump nằm trong `db/recipe_a3/`, lưu bằng Git LFS. Có hai cách dựng lại:

**Cách 1 (khuyên dùng):** restore `db/recipe_a3/`, bản dump của A3.
- Định dạng thư mục của `pg_dump` (`-Fd`), mỗi bảng một file, tổng khoảng 1,3 GB, lưu bằng Git LFS.
- Cài `git lfs` **trước khi clone**. Nếu đã clone rồi thì chạy `git lfs pull`.
- Checksum: `cd db/recipe_a3 && sha256sum -c ../recipe_a3.sha256`.
- Dump không có bảng `chunk_semantic_legacy` và schema `spike`, vì làm tiếp không cần. Hai thứ này vẫn còn trên máy gốc.

Volume mới đã có sẵn schema (do `sql/docker-init.sql` tạo). Restore đè lên schema đó sẽ báo lỗi trùng khóa, nên phải tạo lại DB trống trước:
```
docker compose up -d --wait
docker cp db/recipe_a3 a3-paradedb:/tmp/recipe_a3
docker exec a3-paradedb dropdb -U recipe recipe        # chỉ làm trên volume mới, chưa có dữ liệu
docker exec a3-paradedb createdb -U recipe recipe
docker exec a3-paradedb pg_restore -U recipe -d recipe --no-owner -j 4 /tmp/recipe_a3
docker exec a3-paradedb rm -rf /tmp/recipe_a3
```
- Lệnh restore mất khoảng 2 phút. Nó báo 3 lỗi "schema đã tồn tại" cho `paradedb`, `tiger` và `topology`; các lỗi này vô hại.
- Ngày 15/10 đã thử restore vào một DB trống. Số công thức và số chunk của 3 chiến lược khớp DB gốc, md5 của thẻ cũng trùng.
- Trong Git Bash, thêm `MSYS_NO_PATHCONV=1` trước `docker`.

**Cách 2:** dựng từ `recipe.dump` của A1, rồi chạy lại các bước của A3.
1. Restore `recipe.dump` theo lệnh ở cách 1.
2. Chạy lần lượt `sql/migrations/002-*.sql` đến `005-*.sql`. Dùng `psql -f` bên trong container, đường dẫn `/docker-entrypoint-initdb.d/sql/migrations/...`.
3. Chạy `uv run scripts/tag.py run`.
4. Chạy `uv run scripts/ingest.py retag semantic`. Bước này giữ nguyên embedding, không phải embed lại.

Sau đó so `eval/corpus.json` với bản trong git: số đếm của từng quy tắc phải trùng.

### Kiểm tra
```
uv sync
uv run scripts/check_env.py                    # sinh lại docs/env.md cho máy mới
uv run python -m pytest -q                     # nhanh, khoảng 30 giây, không cần Ollama
uv run python -m pytest -q -m slow             # golden M1 và 4 kịch bản demo, cần Ollama
uv run scripts/chat_cli.py --preset S          # chat thử; /state /trace /reset /quit
uv run uvicorn api.main:app --port 8000        # UI chat ở http://localhost:8000/chat (docs/demo_m4.md)
```

Trên Windows:
- Đặt `PYTHONUTF8=1`.
- Chạy test bằng `uv run python -m pytest`, vì đường dẫn có dấu cách.
- Trong Git Bash, thêm `MSYS_NO_PATHCONV=1` trước các lệnh `docker exec` có đường dẫn.

### Cache LLM (`data/cache/`, có trong git)
- `llm.jsonl`: M1 (golden), khóa theo hash của đầu vào.
- `checker.jsonl`: bộ kiểm `llama3.1:8b` trên 200 mẫu. Chạy lại mất vài giờ trên CPU.
- `lexicon_suggest.jsonl`: gợi ý từ điển ở M1.

Giữ cache để tái lập đúng số liệu M2. Trên máy GPU, Ollama có thể sinh khác chút dù cùng seed, nên đừng xóa cache nếu không định chạy lại.

## 4. Pipeline M3: chỗ nào nằm ở đâu

`api/pipeline/`:

| File | Vai trò |
|---|---|
| `flags.py` | Các cờ và preset B0, B1, S, S−QU, S−Filter, S−Norm, S−Conv, S−Rerank, S−Verify, S+Unknown. Preset chỉ khác cờ, không có nhánh code riêng. |
| `schemas.py` | `Understanding`, `Constraints`, `SessionState`, `RecipeCard`, `Verification`. |
| `llm.py` | Gọi Ollama. Có structured output kèm cache, seed 42; có stream. |
| `lexicon.py` | Từ điển lúc chạy: canonical, alias tiếng Việt, gợi ý `context` và `ask`. |
| `m1_understand.py` | Hiểu truy vấn bằng `qwen2.5:7b`, rồi hậu xử lý tất định (grounding, tín hiệu gỡ ràng buộc, tín hiệu thời gian, quy tắc bổ sung, hỏi lại). Golden: 30/30 (`eval/m1_golden.json`). |
| `m2_state.py` | Trạng thái phiên. Dị ứng giữ cả phiên; ràng buộc khác chỉ áp cho một lượt, trừ khi có "từ giờ". `refine` cộng dồn; `remove` gỡ ràng buộc. |
| `m3_router.py` | Chọn đường đi: retrieve, detail, clarify, chat. |
| `m4_retrieve.py` | BM25 và dense trên phân vùng `chunk_semantic`, lọc trong index bằng `NOT (col @@@ pdb.term_set(..))`, rồi RRF. Đường B0 trùng A1 ở 8/8 truy vấn. |
| `m5_postprocess.py` | Rerank bằng mxbai, gom về cấp công thức, lấy top 5, tạo thẻ ngữ cảnh. |
| `m6_generate.py` | Prompt theo đặc tả 6.4, trích dẫn `[R<id>]`, nêu rõ thẻ "có thể chứa". |
| `m7_verify.py` | Bỏ trích dẫn nằm ngoài ngữ cảnh hoặc vi phạm thẻ chắc chắn; sinh lại tối đa 1 lần. |
| `orchestrator.py` | `Assistant.run_turn` phát các sự kiện `constraints`, `recipes`, `token`, `done` (đúng định dạng SSE 6.5, M4 nối thẳng vào được). Lưu `chat_*` và `session_constraint`, ghi `retrieval_trace` cho từng bước kèm `latency_ms`. |

Khi M7 sửa câu trả lời, `done.answer` chứa bản cuối, và UI phải thay phần đã stream bằng bản này.

## 5. Quyết định đã chốt (đừng làm lại)

- **Gắn thẻ theo thành phần**, không theo tên. Ví dụ: balsamic creme không chứa sữa. Thẻ có hai mức:
  - **Chắc chắn:** dùng để lọc cứng.
  - **Có thể chứa:** chỉ cảnh báo, vì người nấu có thể tự chọn nguyên liệu.
- Phô mai dùng rennet động vật được gắn "có thể không chay".
- Alias tiếng Việt có 4 chế độ: `fixed`, `all` (chanh, hải sản), `context` (bơ, kem, mì), `ask` (hành).
- Nhãn M2 là **nhãn bạc** (Claude Sonnet 5.5, gán mù), không có nhãn vàng.
- Bộ kiểm `llama3.1:8b` được giữ nguyên, kèm hạn chế: recall nhóm cá chỉ 0,69. CVR ở M6 phải nêu điều này.
- Luôn dùng reranker mxbai, không có chế độ nhanh. Mỗi lượt khoảng 60 giây trên CPU.
- Thí nghiệm nặng của M6 chạy trên máy có GPU. Độ trễ báo cáo là độ trễ của máy GPU, và `settings.json` của mỗi run ghi rõ máy chạy.
- Giữ bảng `chunk_semantic_legacy` trong DB. Lần `retag` sau sẽ đổi tên bảng này, không xóa.

## 6. Câu hỏi còn mở

- **Lỗi parser làm lọt chất gây dị ứng** (chi tiết ở mục M3 trong `docs/progress.md`). Ví dụ: `"creamy, low-salt peanut butter"` bị cắt thành "creamy" và vẫn được ghi `ok`. Ảnh hưởng khoảng 190 công thức. Sửa lỗi này nghĩa là đổi bộ gắn thẻ đã duyệt, sau đó phải chạy `retag` và đo lại M2, nên cần Thy duyệt trước.
- Các nhận xét khác từ demo (prompt M6, "gạo nếp" thành `rice`) được ghi ở cùng mục đó.
- Demo M4/M7 chạy trên máy nào (CPU thì chậm). Cần chốt trước M4.
