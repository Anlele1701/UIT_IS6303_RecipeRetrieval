# Nhật ký tiến độ A3

Mỗi mục ghi theo một gate. Số liệu dẫn từ các file sinh tự động (đường dẫn kèm theo), không gõ tay.

---

## M0 – Dựng nền và tái lập A1 (11–12/10/2026) · 🚦 đã duyệt 14/10/2026

### Quyết định ở gate M0 (Thy, 14/10/2026)
1. **Tái lập:** chấp nhận. Run `eval/runs/20261012-002242` là mốc B0 trên máy A3. Báo cáo ghi rằng fusion lệch R@10 −0,013 do index IVF được build lại khi restore, còn bản exact trùng A1 tuyệt đối.
2. **ADR-0005:** chọn cách A (cột `text[]` kiểu `pdb.literal` + `pdb.term_set`). Trạng thái ADR chuyển sang *accepted*.
3. **Độ trễ:** chọn phương án (d), **chạy các thí nghiệm nặng (đánh giá M6, rerank mxbai) trên máy có GPU**. Hệ quả:
   - Repo phải tái lập được trên máy khác: cùng image digest, cùng `recipe.dump`, cùng `uv.lock`, và có `docs/env.md` sinh riêng cho máy đó.
   - Độ trễ báo cáo ở M6 là độ trễ của máy GPU. `settings.json` của mỗi run ghi rõ máy chạy.
   - Còn mở: demo (M4/M7) chạy trên máy nào. Nếu demo trên máy này (CPU) thì mỗi lượt chat sẽ chậm, cần chốt trước M4.
4. **Dọn dẹp:** đã xóa `/tmp/recipe.dump` trong container. **Giữ lại** schema `spike`.

### Việc đã làm
- Tạo repo `recipe-assistant/` từ A1 `tony/` (commit A1 nguồn: `61199ce`). Thư mục A1 không bị sửa (`git status` của A1: 0 thay đổi).
- Tách khỏi A1:
  - Compose project `is603a3`, volume `is603a3_a3-pgdata`, container `a3-paradedb`, port 5435.
  - Dùng cùng image digest với A1 (pg17, pg_search 0.25.9).
  - Test `tests/test_isolation.py` canh không còn chỗ nào trỏ về A1.
- Nạp dữ liệu bằng **restore `recipe.dump` của A1**, không embed lại. Lý do: ước tính embed lại `chunk semantic` mất 3,88 giờ (`eval/env.json`), vượt ngưỡng 3 giờ của kế hoạch.
  - Restore mất khoảng 2 phút.
  - Kết quả: 32.719 công thức, 311.060 dòng nguyên liệu, 3 chiến lược đã nạp. Riêng `semantic` có 166.438 chunk, khớp `corpus.json` của A1.
  - 3 lỗi "schema đã tồn tại" khi restore (paradedb, tiger, topology) là vô hại.
- `pytest`: 134 pass, 1 skip. Test bị skip là test kiểm bundle report của A1, vì nó cần các thư mục run của A1, không copy sang.

### Bảng tái lập (`docs/m0_reproduction.md`, `eval/m0_reproduction.json`)
- **Cấu hình phục vụ (probe 0,02), run `eval/runs/20261012-002242`:**
  - Hybrid/semantic: R@5 0,966, MRR 0,893, nDCG@10 0,914. Lệch so với A1 tối đa 0,003, trong ngưỡng.
  - Fusion: R@10 lệch −0,013, vượt ngưỡng ±0,01. Ba metric còn lại trong ngưỡng.
- **Dense chính xác (probe 1,0), run `eval/runs/20261012-031749`:**
  - Dense và fusion **trùng tuyệt đối** với nhánh `exact-dense` của A1.
  - Rank của công thức đúng trùng ở 298/298 truy vấn.
  - Embedding chunk embed lại trên máy này cho cosine 1,00000 so với vector lưu trong dump.
- **Giải thích:** dữ liệu, embedding và code giống hệt A1. Chênh lệch ở probe 0,02 là do pg_restore build lại index IVF (k-means), nên cụm khác với index của A1. Đây là nhiễu của bước ANN đã nêu trong ADR-0003, không phải lỗi tái lập.

### Spike lọc mảng (ADR-0005, `eval/spike/array_filter_{synthetic,real}.json`)
- Trên 166.438 chunk thật, cả 3 cách lọc đều chạy trong ParadeDB Custom Scan (Top-K):
  - 0 vi phạm, 0 truy vấn hụt.
  - BM25 trùng 100% với đáp án tính trực tiếp không qua index.
  - Overlap dense với exact không thấp hơn khi không lọc.
- **Đề xuất:** cột `text[]` kiểu `pdb.literal` + `NOT (col @@@ pdb.term_set(...))`. BM25 có lọc khoảng 8 ms, so với 6,6 ms khi không lọc.
- `&&` chạy dạng `heap_filter`, chậm hơn khoảng 4 lần. `=== ANY` bị lỗi CBOR trên bản 0.25.9.
- *Đính chính đầu M1 (14/10):* biến thể tổ hợp `D_combined` (thêm thời gian và danh mục) ban đầu lọc sai tên danh mục, nên đáp án rỗng. Sau khi sửa và chạy lại, biến thể này đạt đủ tiêu chí. Số mới ở `eval/spike/array_filter_real.json`.

### Môi trường và độ trễ (`docs/env.md`, `eval/env.json`, `eval/latency_probe.json`)
- Máy chỉ có CPU (Ryzen AI 7 350, 31 GB RAM). Ollama 0.40.3 **không nhận iGPU Radeon 860M**: chạy với `OLLAMA_VULKAN=1` vẫn ở CPU, tốc độ 8,2 so với 8,5 token/giây.
- `qwen2.5:7b` sinh khoảng 8,8 token/giây, `llama3.1:8b` khoảng 8,0 token/giây.
- **Reranker mxbai-base trên CPU** (50 ứng viên thật, 10 truy vấn):
  - p50 khoảng 31 giây.
  - Rerank 20 ứng viên: khoảng 15 giây.
  - MiniLM-L6: 0,4 giây với 50 ứng viên, 0,18 giây với 20 ứng viên.
- Chất lượng theo các nhánh ablation của A1 (hybrid/semantic):
  - mxbai: MRR 0,895, nDCG@10 0,916.
  - MiniLM-L6: MRR 0,799, nDCG@10 0,837.
- Embed một truy vấn mất khoảng 20 ms khi model đã nạp, nhưng mất khoảng 2 giây nếu Ollama phải nạp lại model. Trong run hybrid, p50 embed là 2 giây vì model bị đẩy ra khỏi bộ nhớ: lúc đo chỉ còn khoảng 1–6 GB RAM trống, do Docker được cấp 15 GB và các container `ocs-prestodemo` của Thy đang chạy.

### Sai khác so với kế hoạch build
1. Copy thêm từ A1: `eval/queries.jsonl`, `eval/qrels.csv`, các file nhãn A1, `report.html` và một `per_query.csv`, để `evaluate.py` và test của A1 chạy được. Run tham chiếu được lưu trong `eval/a1_reference/`.
2. Ghim Python 3.12 (`.python-version`). Nếu không ghim, uv tự chọn 3.14.
3. Spike dùng mảng `ingredients_norm` + `term_set` cho nguyên liệu, thay cho cột text `ing_tokens`. Cách này tương đương nhưng gọn hơn.
4. Nạp dữ liệu bằng `pg_dump` thay vì embed lại, theo phương án thay đã có trong kế hoạch build.

### Cần Thy quyết ở gate M0
1. **Duyệt bảng tái lập.** Hybrid khớp. Fusion R@10 −0,013 do index ANN build lại, còn bản exact trùng tuyệt đối. Có chấp nhận cách giải thích này không?
2. **Duyệt ADR-0005** (`pdb.literal` + `term_set`), để đổi trạng thái sang *accepted*.
3. **Độ trễ trên CPU** ảnh hưởng mục tiêu ở M3: rerank 31 giây cộng sinh khoảng 200 token (khoảng 23 giây). Các hướng có thể chọn:
   - (a) Giữ mxbai cho các thí nghiệm offline, nhưng UI và demo dùng ít ứng viên hơn hoặc reranker nhỏ hơn. Phải báo cáo rõ hai chế độ này.
   - (b) Đổi reranker mặc định của A3 sang một model nhanh hơn. Nhưng B0 (A1 Hybrid) phải giữ đúng mxbai để so sánh công bằng.
   - (c) Thử chạy mxbai bằng ONNX Runtime hoặc lượng tử hóa int8 ở đầu M3, đo lại rồi mới quyết.
   - (d) Chạy thí nghiệm trên máy có GPU, nếu nhóm có.
   - Ngoài ra, nên tắt các container không liên quan khi chạy đánh giá để giải phóng RAM.
4. **Xóa schema `spike`** trong DB A3 (vài trăm MB) hay giữ lại.

---

## M1 – Pipeline dữ liệu · ⏸ tạm dừng theo yêu cầu của Thy (14/10/2026)

**Điểm dừng:**
- Thy đã chốt mức thẻ cho từng nhóm (bảng ở `docs/review_m1.md`, mục 3) và 14 gợi ý đồng nghĩa (nhận 12).
- Nguyên tắc: gắn thẻ theo thành phần thật, không theo tên.
- **Còn chờ:** Thy duyệt `vi_alias.csv`. Mình sẽ hỏi từng từ đa nghĩa trong chat, ví dụ bơ, chanh, kem, hải sản, hành, mì. File này không ảnh hưởng thẻ.
- **Bước kế tiếp khi tiếp tục:**
  1. `tag.py run`.
  2. `ingest.py retag semantic`.
  3. Kiểm trước và sau (probe 1,0).
  4. Gate M1.


### Đã xong (commit mới nhất `81680f4`)
- **D4 parser:** 96,5% dòng `ok`, 3,5% `partial`, ≈ 0% `fail`.
- **D5 từ điển:**
  - 1.984 canonical: 51 nhóm viết tay, top 1.500 tên lõi, cộng mọi cụm từ trong `rules.csv`.
  - **99,2%** số dòng ánh xạ được.
- **D6–D7:** `rules.csv` gồm nhóm thực phẩm và dị ứng, khớp cụm dài nhất trước, có ngoại lệ. Cờ chế độ ăn xét cả nhóm thực phẩm lẫn thẻ dị ứng.
- **D8:** 2.388 dòng `unknown`; 6,5% công thức có ít nhất một dòng `unknown`. Mình đã tự rà toàn bộ phần đuôi `unknown` để bắt các từ có thịt, cá hoặc dị ứng.
- **Từ điển tiếng Việt `vi_alias.csv`:** 276 alias, kèm bản không dấu.
- **Schema:**
  - Thêm các bảng thẻ (`sql/tags.sql`), migration 002 (đã áp lên DB), và cột thẻ trên `chunk`.
  - `ingest.py retag` (chưa chạy trên DB thật, chờ từ điển được duyệt).
- **`scripts/tag.py`** ghi `eval/corpus.json` và `docs/corpus_report.md`. Số liệu hiện tại là **trước khi Thy duyệt**.
- `pytest`: 258 pass, 1 skip.
- **Phát hiện mới:** pg_search 0.25.9 không chạy được toán tử term theo trường qua bảng cha đã chia phân vùng (phụ lục ADR-0005).

### 👤 Thy đang làm
Duyệt theo `docs/review_m1.md`:
- Khoảng 17 dòng đầu `synonym_suggestions.csv`.
- `vi_alias.csv`.
- Khoảng 100 dòng đầu `allergen_map.csv`, ghi nhận xét vào cột `review`.

### Sau khi Thy duyệt (mình làm)
1. `apply-suggestions`, chuyển nhận xét ở cột `review` thành quy tắc, `bootstrap`, `make_vi_alias`.
2. `tag.py run`.
3. `ingest.py retag semantic`. Phân vùng cũ được giữ lại dưới tên `chunk_semantic_legacy`.
4. Kiểm trước và sau: chạy dense và fusion ở probe 1,0. Kết quả phải trùng run `20261012-031749`.
5. Commit số liệu và dừng ở 🚦 gate M1.

### Quyết định để ngỏ (không chặn M1)
1. **M4 truy vấn thế nào** (ADR-0005, phụ lục):
   - (a) Truy vấn thẳng vào phân vùng và dùng `term_set` (đề xuất).
   - (b) Truy vấn qua bảng cha và dùng `&&`.
2. **Sản phẩm ghi "gluten-free", "dairy-free"…** Hiện vẫn gắn nhóm dị ứng gốc (bảo thủ). Ví dụ "gluten-free pasta" vẫn bị gắn lúa mì.
3. **Mốc B0:** `retag` build lại index, nên B0 phải chạy lại trên index mới ở M6. Run `20261012-002242` chỉ còn là bằng chứng tái lập của M0.
