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

## M1 – Pipeline dữ liệu · ✅ gate M1 đã duyệt (14/10/2026)

### Quyết định ở gate M1 (Thy, 14/10/2026)
1. **Duyệt** phân bố thẻ và tỉ lệ `unknown`. M1 đóng.
2. **Xóa `chunk_semantic_legacy`** (1.479 MB) ngay. Đã xóa. Nếu cần lại, dữ liệu vẫn khôi phục được từ `recipe.dump`.
3. **M4 đọc thẳng vào phân vùng `chunk_<strategy>`** và lọc bằng `NOT (col @@@ pdb.term_set(...))` cho mọi cấu hình, cả B0 lẫn S. ADR-0005: phương án (a).
4. **B0 chạy lại ở M6 trên index mới**, cùng index với hệ S. Run M0 `20261012-002242` chỉ còn là bằng chứng tái lập.


### Số liệu chính (`eval/corpus.json`, `docs/corpus_report.md`)
| Quy tắc | Kết quả |
|---|---|
| D1 | 32.722 dòng CSV → bỏ 3 URL trùng → 32.719 công thức |
| D2 | Bỏ 13 cột dinh dưỡng; cột ít rỗng nhất vẫn rỗng 99,4% |
| D3 | `total_time` null ở 1.859 công thức (1.832 rỗng ở nguồn, 27 không đọc được) |
| D4 | 311.060 dòng: ok 96,5%, partial 3,5%, fail ≈ 0% |
| D5 | 2.000 canonical; **99,3%** số dòng ánh xạ được; 9.637 dòng chứa nhiều nguyên liệu |
| D6 | 27.791 công thức có ít nhất một nhóm dị ứng **chắc chắn**. Thẻ "có thể chứa" chỉ dùng để cảnh báo, ví dụ: 1.724 công thức chỉ có thể chứa đậu nành, 233 chỉ có thể chứa sữa |
| D6b | 128 dòng ghi "X-free" ở 118 công thức được gỡ nhóm X |
| D7 | vegetarian 51,0%, vegan 12,7% (279 / 77 công thức chỉ đạt khi bỏ qua thẻ "có thể") |
| D8 | 2.244 dòng `unknown`; 6,1% công thức có ít nhất một dòng `unknown` |

### Quyết định của Thy trong M1
- Gắn thẻ **theo thành phần thật**, không theo tên. Nhận 12/14 gợi ý đồng nghĩa của LLM.
- **Thẻ hai mức:** "chắc chắn" dùng để lọc cứng; "có thể chứa" chỉ cảnh báo, vì người nấu có thể chọn nguyên liệu khác. Mức của từng nhóm nằm ở `docs/review_m1.md`, mục 3.
- **"X-free":** gỡ nhóm X khỏi dòng ghi "X-free". Ngoại lệ: non-dairy và lactose-free.
- **Từ tiếng Việt đa nghĩa:**
  - chanh → cả lime và lemon.
  - bơ, kem, mì → M1 chọn theo ngữ cảnh món.
  - hành → hỏi lại người dùng.
  - hải sản → cá, giáp xác và nhuyễn thể.
  - Từ ngắn chỉ tra trong cụm ràng buộc.
- Giữ cả 3 phân vùng. `fixed` và `sentence` có cột thẻ để NULL.

### Đưa thẻ xuống `chunk` (`ingest.py retag semantic`, 2 phút 12 giây)
- 166.438/166.438 chunk giữ nguyên id, nội dung và embedding. Thẻ khớp `recipe_tag` (0 lệch).
- Phân vùng cũ được giữ lại dưới tên `chunk_semantic_legacy`, chưa xóa.
- **Kiểm lọc:** `NOT (allergens @@@ pdb.term_set(['peanut','milk']))` trên `chunk_semantic` ra 12.667 công thức, đúng bằng số tính từ `recipe_tag`, 0 vi phạm.
- **Kiểm trước và sau** (`eval/m1_retag_check.json`, probe 1,0):
  - Metric dense và fusion **trùng tuyệt đối** run M0.
  - Rank trùng 298/298.
  - Top-20 trùng 297/298 (dense) và 296/298 (fusion).
  - Tính khoảng cách bằng SQL thường trên phân vùng mới và trên legacy cho kết quả trùng nhau, nghĩa là dữ liệu không đổi.
- **Phát hiện:** ngay cả ở probe 1,0, tìm vector của ParadeDB **vẫn xấp xỉ**. Ví dụ q080: công thức 16048 có trong top-50 khi tính chính xác bằng SQL nhưng index bỏ sót. Nhánh "exact-dense" của A1 (ADR-0003) vì thế không hoàn toàn exact. Cần ghi vào báo cáo.

---

## M2 – Bộ 200 mẫu, bộ kiểm độc lập, P/R · ✅ gate M2 đã duyệt (15/10/2026)

### Đã xong
- **Mẫu 200 công thức**, phân tầng theo danh mục, gồm 150 mẫu dev và 50 mẫu holdout (`eval/labels/allergen_sample.csv`, seed 42/43/44).
- **Công cụ gán nhãn mù** `scripts/audit_tool.py` và hướng dẫn `docs/annotation_guide.md`.
- **Nhãn:** `eval/labels/allergen_gold.csv` là **nhãn bạc**. Claude Sonnet 5.5 gán, mù, có Thy hướng dẫn. Không có nhãn vàng (Thy quyết định). Nguồn gốc ghi ở `allergen_gold.provenance.json`.
  - Hệ quả: tiêu chí G4 đổi thành "P/R so với nhãn bạc".
  - Phần hạn chế phải nêu rủi ro cùng họ Claude: quy tắc của bộ gắn thẻ do Opus viết, nhãn bạc do Sonnet gán.
- **Bộ kiểm độc lập** `scripts/checker.py` (`llama3.1:8b`), có test chứng minh độc lập. Đã chạy 20/200 công thức. Cache theo từng ràng buộc nằm ở `data/cache/checker.jsonl` (220 dòng).
- **Lý giải thiết kế** so với Elkiran & Rasheed (2026): `docs/design_rationale_retrieval.md`, kèm kiểm chứng `eval/similarity_check.json`.

### Chạy tiếp khi mở máy (từ `A3/recipe-assistant/`)
```sh
docker compose up -d --wait
"$LOCALAPPDATA/Programs/Ollama/ollama.exe" serve &     # hoặc mở app Ollama
PYTHONUTF8=1 uv run scripts/checker.py sample           # tiếp từ cache, còn khoảng 180 công thức × 30 giây ≈ 1,5 giờ
```

### Việc còn lại
1. Chạy xong bộ kiểm.
2. `scripts/eval_allergen.py`: P/R kèm Wilson CI cho bộ gắn thẻ (mức chắc chắn, và mức chắc chắn + có thể) và bộ kiểm (strict / lenient), so với nhãn bạc. Có ma trận bất đồng. Lỗi chỉ liệt kê trên tập dev.
3. Gate M2.

### Quyết định ở gate M2, vòng 1 (Thy, 15/10/2026)
- **Phô mai dùng rennet động vật** (Parmesan, Romano, Pecorino, Gruyère, Asiago…) → **có thể không chay**: vẫn gắn cờ vegetarian, kèm cảnh báo `diet_may`. Đây là lần lặp 1 của từ điển, dựa trên tập dev. Đã gắn lại thẻ phân vùng semantic, 0 lệch.
- **Bộ kiểm:**
  - Sửa lỗi JSON: hỏi theo lô 6 câu, thử tối đa 3 lần; trạng thái `error` được ghi riêng.
  - Bổ sung kiến thức chung về thành phần ẩn vào prompt.
  - Chạy lại trên 200 mẫu. Holdout chỉ đo lại một lần.
- **Giữ `chunk_semantic_legacy`** (bản trước lần gắn thẻ lại ở M2), để dùng nếu sau này đổi phương án. Lần `retag` sau sẽ **đổi tên** bản legacy hiện có thành `chunk_<strategy>_legacy_<thời điểm>` để giữ lại, không xóa (Thy, 15/10/2026).

### Kết quả và quyết định đóng gate M2 (Thy, 15/10/2026)
Số liệu lấy từ `eval/labels/report_allergen.{json,md}`, lần lặp 1, so với **nhãn bạc**, toàn bộ 200 mẫu, nhãn "Có".

- **Bộ gắn thẻ: duyệt.** Từ điển chốt ở lần lặp 1.
  - P/R từ 0,97 đến 1,00 cho 8/9 nhóm dị ứng.
  - Đậu nành: R = 0,50 với thẻ chắc chắn, 0,79 khi tính cả thẻ "có thể".
  - Không chay: R = 0,91 với thẻ chắc chắn, 0,99 khi tính cả thẻ "có thể".
  - Lưu ý: nhãn bạc và quy tắc của bộ gắn thẻ cùng họ Claude, nên con số có thể bị thổi phồng.
- **Bộ kiểm `llama3.1:8b`, lần lặp 1: giữ nguyên, nêu hạn chế trong báo cáo** (Thy). Kết quả chế độ strict:

  | Nhóm | Recall | Precision |
  |---|---|---|
  | Sữa | 0,98 | 0,85 |
  | Cá | **0,69** | 0,76 |
  | Giáp xác | 0,82 | 0,82 |
  | Lúa mì | 0,94 | 0,81 |
  | Đậu nành | 0,79 | 0,34 |

  - Dòng bằng chứng hợp lệ: 0,85.
  - Ví dụ lỗi: model trả "no" cho những món hiển nhiên có cá (salmon). Ba cách hỏi khác đã thử trên dev đều không sửa được.
  - CVR ở M6 cho nhóm cá phải kèm cảnh báo về recall này. Báo cáo cả hai biến thể CVR strict và lenient.
- **Ghi chú về tính khách quan:**
  - Lỗi chỉ được xem trên tập dev.
  - Con số tổng của holdout đã được xem ở lần lặp 1.
  - Không chỉnh gì thêm sau thời điểm đó.
- **Tiêu chí G4** được diễn đạt lại thành "P/R so với nhãn bạc (Claude Sonnet 5.5, mù)".

---

## M3 – Pipeline hội thoại M1–M7 (15/10/2026) · ⏸ code xong, chưa qua gate

Bàn giao sang máy khác: xem `docs/handoff.md`.

### Quyết định đầu M3 (Thy, 15/10/2026)
- Thêm trường `remove` vào schema M1, để người dùng gỡ ràng buộc bằng lời. Đây là sai khác so với mục 6.1.
- Luôn dùng reranker mxbai, không có chế độ nhanh.

### Việc đã làm
- `api/pipeline/`: `flags`, `schemas`, `llm`, `lexicon`, `m1_understand` … `m7_verify`, `orchestrator`. Bảng chat ở migration 005.
- `scripts/chat_cli.py`: chat nhiều lượt; có lệnh `/state`, `/trace`, `/reset` và tham số `--preset`.
- **Golden M1** (`eval/m1_golden.json`): 30/30 câu đúng mọi slot. Lần chạy đầu được 28/30, sau đó thêm 2 quy tắc tất định: "thuần chay" thành vegan, và "nut" chung chung thì thêm cả peanut.
- **M4:**
  - Đường B0 trùng `fused_candidates` của A1 ở 8/8 truy vấn.
  - Khi lọc bằng thẻ: 0 công thức vi phạm thẻ chắc chắn.
  - S−Norm (ILIKE): còn 1 vi phạm. Đây là kết quả dự kiến của nhánh yếu hơn.
- **M7:** câu trả lời không trích dẫn món nào vẫn được tính là hợp lệ. Nhờ vậy câu từ chối đúng ("không có món phù hợp") không bị ép phải trích dẫn.
- **Test:**
  - `pytest` nhanh: 341 pass.
  - `-m slow`: golden M1 và 4 kịch bản demo đều pass (11 phút trên CPU). Kết quả ở `eval/m3_demo.json`.

### Nhận xét từ 4 kịch bản demo (để xử lý ở gate M3)
1. **Lỗi parser làm lọt chất gây dị ứng** (phát hiện ở kịch bản 1):
   - Hiện tượng: R18880 "Chicken Stir-Fry with Thai Peanut Sauce" lọt qua bộ lọc đậu phộng. Dòng `"creamy, low-salt peanut butter"` bị cắt ở dấu phẩy thành "creamy"; dòng `"unsalted, dry-roasted peanuts"` thành "unsalted". Cả hai dòng không khớp nguyên liệu nào nhưng vẫn được ghi `parse_status = ok`, nên cũng không bị tính là `has_unknown`.
   - Quy mô: khoảng 196 dòng ở 190 công thức chỉ còn lại một tính từ. 44 dòng không khớp nguyên liệu nào có chứa từ chỉ chất gây dị ứng (đếm bằng SQL, 15/10).
   - **Cần quyết định:** sửa quy tắc dấu phẩy (khi phần trước dấu phẩy chỉ toàn tính từ thì lấy phần sau) và chuyển dòng không khớp nguyên liệu nào sang `fail`. Sau đó chạy `retag`, rồi đo lại M2 trên các mẫu bị ảnh hưởng. Việc này đổi bộ gắn thẻ đã duyệt, nên chưa làm.
2. Câu trả lời có trích R18880 nhưng ghi rõ "không phù hợp vì chứa đậu phộng". M7 không bỏ trích dẫn này, vì nó chỉ kiểm thẻ.
3. "không gạo nếp" bị M1 chuyển thành loại `rice` (rộng hơn ý người dùng), nhưng món xôi xoài vẫn lọt, có lẽ vì canonical là "sticky rice". Cần xem lại cách ánh xạ cho các nguyên liệu con.
4. Câu trả lời tiếng Việt đôi khi chép nguyên định dạng thẻ ngữ cảnh (`| 55 phút |`). Cần chỉnh prompt M6.
5. Độ trễ trên CPU: 28 giây (chat) đến 109 giây (có sinh lại) mỗi lượt.

### Việc còn lại trước gate M3
- Thử khoảng 20 câu bằng `chat_cli`, ghi lỗi.
- Quyết định cách xử lý lỗi parser ở mục 1.

---

## MV0 – Inventory hồ sơ bệnh nhân C-CDA (17/10/2026) · 🚦 đã duyệt 17/10/2026

Đặc tả: `docs/plan/A3_vectorless_ho_so.md`. Chạy song song với gate M3 (đã được duyệt trong kế hoạch MV0). Số liệu ở `eval/patient_inventory/summary.json` và `docs/patient_inventory.md`, sinh bởi `scripts/patient_inventory.py`.

### Việc đã làm
- `api/patient/ccda.py`: đọc C-CDA bằng `lxml`, nhận diện section theo LOINC, các quy tắc "đang hiệu lực" ở mục 2.2. Ngày hiện tại lấy từ `effectiveTime` của hồ sơ. Không đọc tên, địa chỉ, chủng tộc.
- `scripts/patient_inventory.py`: quét toàn bộ thư mục, ghi các bảng mã kèm số đếm. Kết quả không chứa tên, tên file hay mã bệnh nhân.
- `data/rules/allergy_substance.csv` (bản nháp `draft-mv0`): 7/7 chất dị ứng thực phẩm có trong dữ liệu. Mọi tên trong `extra_ingredients_exclude` đều có trong bảng `ingredient`.
- Thêm `lxml` vào dependency, `PATIENT_DATA_DIR` vào `api/config.py`. Thư mục dữ liệu đưa vào `.gitignore`, chỉ commit một file mẫu làm fixture.
- Test: `tests/patient/test_ccda_inventory.py`, 13 test. `pytest` nhanh: 354 pass.

### Phát hiện chính
- 108 file, parse được hết, 108 mã bệnh nhân khác nhau. `softwareName` không có số phiên bản.
- **8 bệnh nhân đã mất** (có organizer giấy chứng tử `69409-1`). Ngày hồ sơ của họ là ngày cũ (từ 1961), nên quy tắc "đang hiệu lực" tính theo ngày đó.
- Ứng viên tầng P8 (lần quét đầu, còn tính bệnh nhân đã mất): dị ứng thực phẩm 11, tiểu đường 8, tăng huyết áp 20, CKD 6, đa bệnh 7, không ràng buộc 74.
- **Không có** huyết áp tâm thu/tâm trương (`8480-6`, `8462-4`) và HbA1c (`4548-4`) trong dữ liệu. eGFR, natri, kali chỉ có ở 10–17 bệnh nhân.
- Mọi mã khởi đầu của đặc tả ở bảng 4.1–4.3 đều có trong dữ liệu. Ngoài ra còn có CKD giai đoạn 1–2, các biến chứng tiểu đường type 2, tăng lipid máu và thiếu máu.

### Cần Thy quyết định trước MV1
1. Ngưỡng số bệnh nhân cho từng tầng P8, vì CKD chỉ có 6 và tiểu đường 8.
2. Có giữ 8 bệnh nhân đã mất trong tập đánh giá không. Organizer giấy chứng tử có nên đưa vào danh sách loại trừ P7 không.
3. Duyệt bản nháp `allergy_substance.csv`, nhất là việc mở rộng Shellfish sang 19 tên nhuyễn thể.
4. Duyệt danh sách đề xuất cho `exclude_loinc.csv` (7 bảng hỏi sàng lọc, mục 7 của `docs/patient_inventory.md`).
5. Câu hỏi 4 ở mục 11 của đặc tả: có cần thêm ghi chú tự do Asclepius không, hay chế độ `narrative` là đủ.

### Quyết định sau MV0 (Thy, 17/10/2026)
1. **Phân tầng P8:**
   - Không đặt mức tối thiểu cứng. Lấy toàn bộ bệnh nhân tầng CKD và tiểu đường, không lấy mẫu ở hai tầng này.
   - Kết quả theo tầng chỉ báo cáo mô tả (n và khoảng tin cậy), không kiểm định riêng.
   - Bootstrap lấy mẫu theo bệnh nhân, không theo câu hỏi.
   - Tùy chọn: sinh thêm bệnh nhân bằng Synthea (lọc theo module, seed cố định) cho đủ 15–20 người mỗi tầng, kèm cột `source = sample | generated`.
2. **Bệnh nhân đã mất:**
   - Vẫn nạp, gắn `deceased = true` và đếm ở P1, nhưng loại khỏi tập đánh giá P8.
   - API và chat CLI từ chối mở phiên cho bệnh nhân đã mất (làm ở MV3).
   - Giấy chứng tử (`69409-1`) thuộc P7.
3. **`allergy_substance.csv`:** duyệt cả 7 dòng, `version = v1` sau khi kiểm tra bộ gắn thẻ. Fish và sesame chưa có trong dữ liệu nên để `unmapped`.
4. **Organizer:**
   - Dùng danh sách cho phép `include_loinc.csv` (9 mã).
   - `exclude_loinc.csv` gồm 8 mã nhạy cảm, dùng để thống kê P7 và làm test.
   - Organizer còn lại là `not_relevant`. Chưa có luật suy tim nên chưa cho phép `55405-5`.
5. **Asclepius:** không bắt buộc, chế độ `narrative` là đủ cho RQ5. Báo cáo phải ghi `<text>` của C-CDA là bảng bán cấu trúc. Chỉ thêm khoảng 30 ghi chú Asclepius nếu xong MV4 sớm; nếu không thì ghi vào mục 4.6 (hạn chế).

### Đã làm theo quyết định (17/10/2026)
- **Kiểm tra bộ gắn thẻ** (truy vấn DB, chỉ đọc):
  - Đã gắn `milk`: sữa dê, sữa cừu, feta, goat cheese, pecorino, manchego, roquefort.
  - Đã gắn `wheat`: spelt, farro, durum, semolina, bulgur.
  - Đã gắn `egg`: trứng cút.
  - Không có trong kho công thức: kamut, trứng vịt, cuttlefish, cockle, whelk.
  - **`conch` không mang thẻ dị ứng nào**, nên đã thêm vào `extra_ingredients_exclude` của Shellfish (tổng 20 tên).
- Tạo `data/rules/include_loinc.csv` (9 mã) và `data/rules/exclude_loinc.csv` (8 mã).
- Sửa inventory:
  - gộp nhóm theo mã, không theo tên (24321-2 trước bị đếm hai lần);
  - phân loại organizer theo hai danh sách trên;
  - loại bệnh nhân đã mất khỏi tầng P8;
  - đếm số bệnh nhân theo LOINC trên mọi organizer (eGFR: 21, lần trước ghi 17 là sai).
- HbA1c: không có mã nào (`4548-4`, `17856-6`, `4549-2`, `41995-2`) trong 108 file. eGFR (`33914-3`) có ở 21 bệnh nhân, trong organizer `24321-2` và `24323-8`. Glucose máu (`2339-0`) có ở 43 bệnh nhân.
- Test: 16 test trong `tests/patient/`.
- **Ứng viên P8 khi đã loại người đã mất:** dị ứng thực phẩm 11, tiểu đường 5, tăng huyết áp 18, CKD 4, đa bệnh 5 (`eval/patient_inventory/summary.json`).

### Để làm ở mốc sau
- MV1: cờ `deceased` trong bảng `patient`; cây hồ sơ chỉ lấy organizer trong `include_loinc.csv`; thống kê P7 theo `exclude_loinc.csv`.
- MV3: API và chat CLI từ chối bệnh nhân đã mất; test "không mã nào trong `exclude_loinc.csv` xuất hiện trong prompt".
- MV4: chốt có sinh thêm bệnh nhân bằng Synthea hay không.

### Sửa quyết định P8 (Thy, 17/10/2026, thay cho mục 1 ở trên)
- Sau khi loại người đã mất, các tầng còn lại là tiểu đường 5, CKD 4, tăng huyết áp 18, đa bệnh 5. Số này không đủ để báo cáo theo tầng.
- **Bắt buộc sinh thêm bệnh nhân Synthea**, mục tiêu ≥ 15 người còn sống mỗi tầng (tăng huyết áp đã đủ).
- Cách sinh:
  - Sinh một quần thể lớn với cấu hình mặc định, rồi chọn bệnh nhân theo mã bệnh.
  - **Không** dùng bộ lọc module `-m`, vì hồ sơ sẽ thiếu dị ứng và các bệnh khác, khác hẳn bộ mẫu.
  - Giới hạn tuổi (ví dụ `-a 40-90`).
  - Chỉ giữ người còn sống (dùng tùy chọn trong `synthea.properties` của phiên bản đang dùng).
  - Xuất C-CDA bằng cùng phiên bản Synthea với bộ mẫu, seed cố định, ghi lệnh chạy vào `docs/env.md`.
- Lưu ở `data/synthea_generated_ccda/`, gắn cột `source = sample | generated`.
- Báo cáo:
  - Kết quả chính tính trên toàn bộ bệnh nhân.
  - Thêm một bảng chỉ trên `sample` để kiểm tra độ nhạy.
  - Bootstrap theo bệnh nhân.
- Thời điểm:
  - Chốt số lượng ở MV4.
  - **MV1:** ingest phải đọc được nhiều thư mục và có cột `source`.
  - Phải sinh xong trước khi đóng băng bộ câu hỏi.

**Vướng mắc (17/10):**
- File mẫu không ghi phiên bản Synthea. `softwareName` và `assigningAuthorityName` chỉ là URL GitHub, và không có comment hay thuộc tính nào chứa phiên bản.
- Ngày hồ sơ của người còn sống là 18–25/08/2026, nên bộ mẫu có lẽ được sinh khoảng cuối tháng 8/2026.
- Máy này chưa có Java, mà Synthea cần Java 17 trở lên.

**Đã xác định phiên bản Synthea của bộ mẫu (17/10):**
- Nguồn tải: https://synthea.mitre.org/downloads, mục "100 Sample Synthetic Patient Records, C-CDA" (latest). File là `downloads/latest/synthea_sample_data_ccda_latest.zip` trong repo `synthetichealth/synthea-sample-data`.
- Commit mới nhất của file đó: `9959d9178e` (18/08/2026), message "Update from https://github.com/synthetichealth/synthea/commit/d9d07a6eef91ee5144293b42ab64224d84d124f8".
- Đã tải zip ở commit `9959d9178e` và so sha256: **108/108 file trùng** với `data/synthea_sample_data_ccda_latest/`.
- Vậy bộ mẫu sinh từ **Synthea commit `d9d07a6eef91ee5144293b42ab64224d84d124f8`**. Đây là tag `master-branch-latest` tại 18/08/2026, mới hơn bản `v4.0.0` (05/03/2026).
- Khi sinh thêm bệnh nhân: checkout đúng commit này và build từ mã nguồn (không dùng jar `v4.0.0`). Cần Java 17 trở lên.

---

## MV1 – Parse C-CDA và dựng cây hồ sơ (17/10/2026) · 🚦 đã duyệt 17/10/2026

Số liệu ở `eval/patient_corpus.json` và `docs/patient_corpus_report.md`, sinh bởi `scripts/patient_ingest.py stats`.

### Quyết định đầu MV1 (Thy, 17/10/2026)
- V1c dùng tóm tắt **template** khi nạp. Tóm tắt LLM đã code và có test, sẽ chạy sau bằng `patient_ingest.py tree --summarize llm`, trên máy GPU hoặc sau khi sinh xong bệnh nhân. Lý do: khoảng 2.000 nút, chạy CPU mất 4–5 giờ.

### Việc đã làm
- `api/patient/models.py`: các kiểu entry, `PatientRecord` (sau P2–P7, không có danh tính), `PatientNode`, `Evidence`.
- `api/patient/rules.py`: nạp các danh sách P7. Báo lỗi khi `include_loinc.csv` và `exclude_loinc.csv` trùng mã.
- `api/patient/ccda.py`: `read_record` áp P2–P7, kèm số đếm theo từng quy tắc.
- `api/patient/tree.py`: dựng cây tất định (root, 4 nút cố định, nút ngữ cảnh `results.<year>` và `encounters.<year>`).
- `api/patient/summarize.py`: tóm tắt template; tóm tắt LLM có cache, lỗi hai lần thì quay về template.
- `sql/patient.sql`, migration 007:
  - bảng `patient` (có `source`, `deceased`), `patient_node`, `patient_profile_cache`;
  - thêm `chat_session.patient_id`, `session_constraint.source` / `evidence`, scope `patient`;
  - **đã áp lên DB `recipe`** (chỉ thêm bảng và cột).
- `scripts/patient_ingest.py load | tree | stats`: đọc nhiều thư mục kèm `source`; trùng `patient_id` thì báo lỗi; file lỗi được liệt kê bằng hash.
- `data/sources.json`: nguồn tải, Synthea commit `d9d07a6`, sha256. `scripts/check_env.py` thêm mục "Nguồn dữ liệu" đọc từ file này (chưa chạy lại `check_env.py`).
- **Luật mới (bản nháp `draft-mv1`, cần Thy duyệt):** `data/rules/exclude_codes.csv` loại theo P7 các mã sau:
  - bệnh: "Dependent drug abuse", "Overdose";
  - lần khám: "Drug rehabilitation and detoxification", "Death Certification";
  - thuốc: buprenorphine/naloxone.

  Các mục này không phải organizer nên `exclude_loinc.csv` không chặn được.
- Test: 4 file mới trong `tests/patient/` (42 test, có test DB). `pytest` nhanh: 383 pass.

### Số liệu chính
- P1: 108 file, 108 parse được, 0 lỗi; 100 còn sống, 8 đã mất.
- Cây trong DB: 108 nút root, 432 nút cố định, 1.983 nút ngữ cảnh (tóm tắt template).
  - MV0 ước tính 1.984. Lệch 1 nút vì một bệnh nhân có lần khám duy nhất năm 2026 là "Death Certification", bị loại theo P7.
- P7 (số organizer bị loại): tâm thần 1.324, sử dụng chất 627, bạo lực 289, tử vong 8, not_relevant 327. Ngoài ra loại 8 lần khám tử vong, 8 lần khám cai nghiện, 3 bệnh và 1 thuốc thuộc nhóm sử dụng chất.
- Quét tên bệnh nhân mẫu và các mã P7 trong `patient_node`, `eval/patient_corpus.json` và báo cáo: 0 kết quả.

### Cần Thy quyết định
1. Duyệt `exclude_codes.csv`. Có nên loại thêm "Admission to hospice" (8 bệnh nhân) không.
2. Có chạy lại `check_env.py` trên máy này không. Lệnh này sẽ ghi đè `docs/env.md` bằng thông tin máy CPU; bản đang commit là của máy gốc.

### Quyết định ở gate MV1 (Thy, 17/10/2026)
1. **`check_env.py`:** không chạy lại, không ghi đè `docs/env.md` của máy gốc.
2. **`exclude_codes.csv` → `v1`:** duyệt cả 5 mục. Thêm:
   - **Admission to hospice**, nhóm `end_of_life`. Kiểm tra: chỉ **4/8** bệnh nhân hospice trùng với nhóm đã mất; 4 người còn sống vẫn ở tập đánh giá. Việc loại chỉ bỏ lần khám đó khỏi cây.
   - **"Unhealthy alcohol drinking behavior (finding)"** (17 bệnh nhân). Mục này vốn đã bị P4 loại; giờ được kiểm trước P4 nên đếm vào P7.
   - Rà toàn bộ XML: các mục rượu và hospice khác ("Assessment using AUDIT-C", "Hospice care") chỉ nằm trong section Surgeries, vốn không được đọc vào cây.
3. **Rượu:** loại hẳn, **không** suy ra ràng buộc "tránh rượu" (bằng chứng hiện trên giao diện sẽ để lộ chẩn đoán). Ghi vào mục hạn chế của báo cáo (4.6).
4. **Nguyên tắc danh sách cho phép cho prompt:** chỉ nội dung đã qua danh sách cho phép mới được đưa cho LLM.
   - Với vấn đề sức khỏe: chỉ những bệnh có dòng trong `condition_nutrient.csv`. Các bệnh khác vẫn ở trong cây nhưng không đưa cho LLM.
   - `exclude_codes.csv` giữ lại để thống kê P7 và làm test.
   - Làm ở MV2 (khi có `condition_nutrient.csv`) và MV3 (V2, M6).

### Sau gate
- `pytest tests/patient`: 42 pass. Đã nạp lại và sinh lại `eval/patient_corpus.json`.
- P7 sau khi cập nhật: `encounter_end_of_life` 8, `problem_substance_use` 9 (tăng từ 3, vì mục rượu giờ đếm ở P7). `(finding)` ở P4 giảm từ 513 xuống 507.

### Đo tỉ lệ công thức qua luật dinh dưỡng (17/10/2026, theo yêu cầu của Thy)
- Tạo `data/rules/condition_nutrient.csv` bản nháp (`draft-mv2`) từ bảng 4.2 của đặc tả, để ngưỡng không bị hardcode trong code. **Vẫn chờ Thy duyệt ở MV2.**
- Phép quy đổi theo mục 4.4 nằm ở `api/patient/nutrition.py`: ngưỡng ngày × `PER_MEAL_FRACTION` (1/3, trong `api/config.py`); ngưỡng % năng lượng không chia.
- `patient_ingest.py stats` ghi `nutrient_rule_pass` vào `eval/patient_corpus.json`, kèm bảng trong `docs/patient_corpus_report.md`.
- Kết quả (trên 32.719 công thức, tỉ lệ qua trong số công thức có số liệu):
  - natri ≤ 667 mg/khẩu phần (mặc định, CKD): 68,9%;
  - natri ≤ 767 mg (tăng huyết áp, tiểu đường): 73,7%;
  - chất béo bão hòa ≤ 6% năng lượng: **17,2%**;
  - chất xơ ≥ 14 g/1000 kcal: **23,2%**;
  - protein ≤ 0,8 g/kg (nặng 70 kg): 68,0%;
  - đường tổng ≤ 10% năng lượng (warn): 56,5%.
- Gộp theo bệnh (ngưỡng chặt nhất cho mỗi chất): tăng huyết áp **12,6%**, tiểu đường **16,6%**, CKD 56,9%.
- Nhận xét:
  - Ngưỡng natri 2.300 mg của tăng huyết áp và tiểu đường **không bao giờ có tác dụng**, vì ngưỡng mặc định 2.000 mg chặt hơn.
  - Chất béo bão hòa và chất xơ là hai luật thu hẹp kho công thức mạnh nhất.

---

## MV2 – Luật và hồ sơ ràng buộc (17/10/2026) · 🚦 chờ duyệt

### Quyết định đầu MV2 (Thy, 17/10/2026)
- Lần khám: LLM chỉ thấy loại chung (`encounter_class.csv`).
- Cột dẫn xuất: đồng ý 4 cột `sat_fat_pct_kcal`, `sugar_pct_kcal`, `fiber_per_1000kcal`, `potassium_mg`.
- Mã bệnh, mở rộng có chọn lọc:
  - Tiểu đường type 2: cả các biến chứng "due to type 2 diabetes".
  - Natri CKD: giai đoạn 1–4 và "disorder of kidney due to diabetes".
  - Protein: chỉ giai đoạn 3–4.
  - Hyperglycemia, tiểu đường do xơ nang: `unmapped`.
- Natri 2.300 mg: giữ, ghi là bị lấn át.

### Việc đã làm
- **Bảng luật `v1`:**
  - `condition_nutrient.csv` (thêm mã đồng nghĩa và cột `note`);
  - `drug_food.csv`: 3 dòng theo bảng 4.3 (warfarin cảnh báo, kèm 10 rau giàu vitamin K đã kiểm có trong bảng `ingredient`; simvastatin và atorvastatin loại bưởi chùm);
  - `encounter_class.csv`: 41 mã → 9 loại;
  - `prompt_vitals.csv`: cân nặng, chiều cao, BMI.
- **Sai khác so với kế hoạch đã duyệt:**
  - **Bỏ loại `prenatal`** trong `encounter_class.csv`. Nhãn này tự tiết lộ việc mang thai, mà mang thai không có luật, nên các lần khám thai được gộp vào `wellness` / `emergency`.
  - **Thêm `mode = unmapped`** trong `condition_nutrient.csv`, để liệt kê hyperglycemia mà không hardcode. Dòng này không lọc, không cảnh báo, không mở danh sách cho phép của prompt.
- `api/patient/rules.py`:
  - nạp toàn bộ bộ luật, `ruleset_version` là hash của 9 file luật;
  - `validate_against_db` báo lỗi khi tên nguyên liệu không có trong bảng `ingredient`, hoặc cột lọc không có trên `chunk`;
  - chất không có cột (phospho) tự chuyển thành `warn`.
- `api/patient/mapping.py`: `build_profile`, hàm thuần. `api/patient/profile_store.py`: cache trong `patient_profile_cache`.
- `api/patient/prompt_view.py`: danh sách cho phép cho prompt. `summarize` (V1c) dùng view này; tóm tắt template của lần khám chỉ nêu loại chung.
- **Migration 006** (4 cột trên `chunk`, đưa vào `sql/indexes.sql`):
  - `ingest.py` tính các cột này ở cả lần build mới lẫn `retag`, dùng chung biểu thức của `api/patient/nutrition.py`;
  - `staging_problems` có thêm phép kiểm lệch.
- **Đã chạy trên DB `recipe`:**
  - Áp migration 006, `ingest.py retag semantic` (115 giây). Phân vùng cũ giữ ở `chunk_semantic_legacy`, không xóa gì.
  - 4 cột khớp `recipe_nutrition`: **0 lệch** trên 166.438 chunk.
  - **Kiểm trước và sau** (`eval/mv2_retag_check.json`, probe 1,0; run `20261017-171008` → `20261017-172133`):
    - metric dense và fusion **trùng tuyệt đối**; rank trùng 298/298;
    - top-20: dense trùng 298/298, fusion trùng 293/298. Năm truy vấn khác nhau đều là công thức kề nhau đổi chỗ trong cùng một tập (riêng q104 khác ở vị trí 20).
    - Nguyên nhân có thể là điểm BM25 hòa nhau, đổi thứ tự sau khi dựng lại index. Không kiểm chứng được vì bản legacy không còn index BM25. Lần retag ở M1 cũng có hiện tượng tương tự (2/298).
- **Sửa lỗi:** `mapping` ban đầu làm tròn ngưỡng (666,67), để lọt 2 công thức có natri nằm giữa 666,667 và 666,67. Giờ lưu giá trị chính xác.
- ADR-0006 (cây vectorless, danh sách cho phép) và ADR-0007 (quy đổi ngưỡng), trạng thái *proposed*.
- Test: 3 file mới (`test_mapping`, `test_rules`, `test_prompt_view`), thêm test 4 cột cho build mới và retag. `pytest` nhanh: 419 pass.

### Số liệu chính (`eval/patient_profiles.json`, 100 bệnh nhân còn sống, ruleset `6fc4e3a7791e`)
- **Bệnh nhân mẫu** (gate): `wheat`, `crustacean_shellfish`, 20 tên nhuyễn thể, natri ≤ 666,67 mg; bằng chứng trỏ đúng act id.
- 37/100 bệnh nhân có ràng buộc ngoài mức mặc định.
- Dị ứng: shellfish 6, trứng 4, hạt cây 3, sữa 2, lúa mì 2, đậu nành 1, đậu phộng 1.
- Bưởi chùm bị loại ở 17 bệnh nhân (statin).
- Ngưỡng dinh dưỡng: natri 100 (mặc định), chất béo bão hòa 18, chất xơ 5, protein theo cân nặng 3.
- Cảnh báo: đường 100, kali 3, phospho 3, vitamin K 1. `unmapped`: hyperglycemia 2.

### Luật mềm cho luật dinh dưỡng quá chặt (Thy, 17/10/2026)
- **Yêu cầu:** ghi vào `eval/patient_profiles.json` tỉ lệ qua của từng luật và của tổ hợp luật cho từng bệnh nhân. Luật nào để lại dưới khoảng 50% kho thì chuyển sang luật mềm. Ghi số liệu và lựa chọn vào ADR-0007 rồi chuyển ADR sang *accepted*.
- **Đã đo** (`rule_pass_rates`, `patient_pass_spread`, `per_patient`; `patient_id` là uuid của Synthea):
  - Dưới 50%: chất béo bão hòa ≤ 6% (17,2%), chất xơ ≥ 14 g/1000 kcal (23,2%).
  - Natri (68,9–73,7%) và protein (63,5–72,8%) vẫn cứng.
- **Đã đổi:** `condition_nutrient.csv` → `v2`, hai luật trên thành `soft`. Profile có thêm `nutrient_soft` và cảnh báo; M5 sẽ xếp hạng theo luật mềm ở MV3. `ruleset_version` mới: `d0d5ba48e03d`.
- **Dị ứng và nguyên liệu bị loại vẫn cứng**, dù sữa (40,1%) và lúa mì (46,6%) dưới 50%: đây là luật an toàn. Đây là cách mình hiểu yêu cầu (quy tắc 50% chỉ áp cho luật dinh dưỡng); cần Thy xác nhận.
- **Tổ hợp theo bệnh nhân:** dưới 50% kho giảm từ 25 xuống **6** bệnh nhân, cả 6 đều do dị ứng. Thấp nhất tăng từ 5,5% lên 18,4%.
- Test chặn: mọi luật `filter` phải ≥ 50% (đọc `eval/patient_corpus.json`). `pytest` nhanh: 421 pass.
- **ADR-0007 → accepted**, kèm bảng số liệu và lựa chọn. ADR-0006 vẫn *proposed*.

---

## MV3 – Nối hồ sơ vào pipeline M1–M7 (17/10/2026) · 🚦 đã duyệt 17/10/2026 (sau vòng 3)

### Việc đã làm
- **Mốc hồi quy chụp trước khi sửa code:** `eval/mv3_regression_baseline.json` (commit `687da10`), do `scripts/regression_snapshot.py` sinh. Chạy hai lần cho kết quả giống hệt nhau.
- **Cờ `profile`, `profile_mode` và preset mới:** `S-Profile`, `P-Direct`, `P-Vectorless`, `P-Vectorless-Fixed`, `P-Vector`. Hai preset cuối báo "làm ở MV4".
- **Phiên có bệnh nhân:**
  - mỗi lượt chạy V1 → V3 → M1 (schema bệnh nhân) → V2 rồi mới đến M2;
  - sự kiện `patient_profile` phát trước `constraints`;
  - trace có thêm `v1`, `v2`, `v3`;
  - bệnh nhân đã mất hoặc không tồn tại bị từ chối mở phiên (`PatientUnavailable`).
- **Nhánh không có bệnh nhân giữ nguyên lời gọi của M3.** Đã kiểm: cache key của M1 trùng với code cũ.
- **M2:** lớp `patient` (scope và source `patient`, có bằng chứng). Tin nhắn chat không gỡ được; khi người dùng thử gỡ, câu trả lời báo cần xác nhận trên giao diện.
- **M4:** ngưỡng dinh dưỡng lọc trong index; `OR col IS NULL` cũng được đẩy vào Tantivy (đã kiểm bằng EXPLAIN).
- **M5:** xếp hạng ổn định theo luật mềm.
- **M6:** khối `PATIENT_PROFILE`, trích dẫn `[H:node_id]`, prompt riêng cho route `patient_info`.
- **M7:** ba kiểm tra mới (vi phạm ngưỡng, gợi ý thứ phải tránh, `[H:…]` không có thật).
- **Migration 008** (loại ràng buộc `nutrient`, `nutrient_soft`) đã áp. `chat_cli.py --patient`, lệnh `/profile`.
- **Test:** 24 test nhanh mới, `pytest` nhanh 445 pass. Test chậm: hồi quy khi không có bệnh nhân, demo có hồ sơ.
- `tests/golden/m1_patient_cases_draft.jsonl`: 8 câu nháp cho nhánh bệnh nhân, **chờ Thy duyệt nhãn**, chưa gắn vào test nào.

### Kết quả theo điều kiện gate
- ✅ **Hồi quy khi không có `patient_id`:** trùng mốc ở cả 9 lượt (intent, route, ràng buộc, notice, danh sách công thức theo thứ tự).
- ✅ **Golden M1 cũ:** 30/30. Demo M3 cũ: 4/4 pass.
- ⚠️ **Demo có hồ sơ** (`eval/mv3_demo.json`):
  - Tăng huyết áp: 0 vi phạm. Luật mềm có tác dụng: 4/5 công thức có chất béo bão hòa ≤ 6%, công thức 18% bị đẩy xuống cuối.
  - CKD giai đoạn 3: 0 vi phạm, áp natri và protein. Câu hỏi về lịch sử chạy V2 với 1 lần gọi (1,1 giây), chọn `results.2025`, `results.2026`, `encounters.2026`.
  - **Dị ứng (Barton704): bộ kiểm báo 3 công thức chứa lúa mì**, trong khi bộ gắn thẻ không gắn:
    - R8897: bằng chứng là "salmon fillets" → bộ kiểm sai;
    - R13999: bằng chứng là "grated Parmesan", `evidence_ok = false` → bộ kiểm sai;
    - R2920: bằng chứng là "Worcestershire sauce" → còn tranh cãi (giấm mạch nha là gluten từ lúa mạch, không phải lúa mì theo FDA).

    Cách chấm ở M2 tính mọi phiếu "yes" là có chứa, nên theo đúng tiêu chí này gate **chưa đạt**. Lượt thứ hai của kịch bản (thử gỡ dị ứng bằng lời) chưa chạy, vì test dừng ở lượt đầu.
- Độ trễ trên CPU: V1, V3 dưới 0,1 giây (đọc từ cache); M1 6–11 giây; cả lượt 33–68 giây.

### Cần Thy quyết định
1. Cách xử lý phiếu "yes" sai của bộ kiểm. Ví dụ:
   - (a) giữ tiêu chí chặt, ghi vào báo cáo như hạn chế của bộ kiểm;
   - (b) phiếu "yes" có `evidence_ok = false`, hoặc bằng chứng không liên quan, phải qua người duyệt trước khi tính là vi phạm;
   - (c) cách khác.
2. Worcestershire: có cần gắn `wheat` ở mức "có thể chứa" không (một số hãng dùng giấm mạch nha).
3. Câu trả lời của route `patient_info` có diễn giải chỉ số xét nghiệm ("có thể cho thấy xu hướng…"). Có cần siết prompt để chỉ nêu số và ngày, không diễn giải không.
4. Duyệt nhãn của 8 câu golden nháp.

### Sau MV3 – mục 1: phân xử phiếu "yes" của bộ kiểm (17/10/2026)
- `scripts/adjudicate.py`:
  - bước tự động loại phiếu bị bộ kiểm tự đánh dấu, và phiếu có bằng chứng không xuất hiện nguyên văn trong dòng thô;
  - phiếu còn lại vào hàng duyệt mù `eval/labels/checker_queue.csv`, và tính là vi phạm cho tới khi có nhãn;
  - báo hai số `cvr_raw` và `cvr_adjudicated`.
- Không import code của bộ gắn thẻ: `tests/test_checker_independence.py` mở rộng để kiểm cả `adjudicate.py`.
- `eval/labels/checker_adjudication.csv`: file mới, có 1 nhãn do Thy quyết định (R2920 Worcestershire = không vi phạm).
- Quy trình ghi ở mục 5 của `docs/annotation_guide.md`. Test: `tests/test_adjudicate.py` (7 test).

### Sau MV3 – mục 2: Worcestershire (17/10/2026)
- `data/lexicon/rules.csv`: không gắn `wheat`, kể cả mức "có thể chứa". Cột `note` của `worcestershire` ghi: "gluten (nếu có) từ giấm mạch nha làm từ lúa mạch; lúa mạch không thuộc nhóm wheat của FDA". Dòng này vốn chỉ gắn `fish` (cá cơm).
- Phiếu R2920 / `allergen:wheat` = không vi phạm, ghi trong `eval/labels/checker_adjudication.csv`.
- Đã chạy lại `scripts/tag.py run`:
  - Phải tải `data/recipe.csv` (64 MB, từ nguồn HuggingFace ghi trong `ingest.py`; thư mục `data/` không vào git), vì script đếm lại D1–D3.
  - md5 của `recipe_tag` (allergens, allergens_may, diet_flags của 32.719 công thức) **trùng trước và sau**. D1–D8 trong `eval/corpus.json` **không đổi**. Vì vậy **không cần retag**.
  - Chỉ `lexicon_sha256` thay đổi, ở 5 file. Bốn file trong số đó không đổi kể từ `e58f96e`, nghĩa là `corpus.json` cũ được sinh trước lần sửa từ điển cuối và ghi sha của bản cũ. Giờ sha đã khớp với các file đang commit.

### Sau MV3 – mục 3: route patient_info (17/10/2026)
- **Prompt (`m6_generate.PATIENT_INFO`)** chỉ cho nêu giá trị, đơn vị, ngày đo, và khoảng tham chiếu nếu hồ sơ có (dữ liệu Synthea hiện không có). Không diễn giải, không nói xu hướng, không gợi ý chẩn đoán. Câu hỏi "có bình thường không" → trả lời rằng việc diễn giải cần bác sĩ, rồi chỉ nêu giá trị.
- **M7, kiểm tra (d)** (tất định, chỉ cho route `patient_info`):
  - mọi con số trong câu trả lời phải khớp một giá trị trong `facts` của nút đã đọc (hoặc trong khối `PATIENT_PROFILE`), ở đúng độ chính xác câu trả lời viết ra ("67.7" khớp 67.68);
  - số trong dấu trích dẫn và số thứ tự danh sách không tính;
  - không khớp → sinh lại tối đa 1 lần, kèm danh sách số sai.
- Test với câu pe02 (mô hình giả): câu trả lời bịa "eGFR 95" bị sinh lại; prompt có quy định không diễn giải. `pytest` nhanh: 455 pass.

### Sau MV3 – mục 4: golden M1 cho bệnh nhân (17/10/2026)
- `tests/golden/m1_patient_cases_draft.jsonl`:
  - thêm trường `remove` (danh sách); 8 câu cũ có `remove: []`;
  - thêm nguyên văn 6 câu pv06–pv10, pe04;
  - pv05 có ghi chú "nút ngữ cảnh chỉ thêm cảnh báo, không đổi bộ lọc".
- 14 câu, tất cả vẫn ở trạng thái `draft`. Có test kiểm định dạng và kiểm rằng không câu nào tự chuyển sang approved.
- **Cần Thy xem:** pv10 ghi `intent: "chat"`, nhưng `chat` là tên route. Intent của M1 chỉ có `chitchat` / `out_of_scope`; câu hỏi về thuốc sẽ là `out_of_scope` → route `chat`. Mình giữ nguyên văn, chờ Thy chốt.

### Sau MV3 – mục 5: câu pe03 (17/10/2026)
- **Giới hạn:** hội thoại chưa hỗ trợ ràng buộc dinh dưỡng. "low-salt" trong câu hỏi không thành bộ lọc natri. Ngưỡng natri chỉ đến từ hồ sơ; ngoài phiên có bệnh nhân thì không có.
- **Phát hiện:** bước bỏ phủ định tất định (`strip_negation`) **giữ** "low-salt". Chính **LLM ở M1** bỏ cụm này khỏi `query_en` (trả về `"pasta"`), ở cả hai nhánh, vì prompt M1 dặn `query_en` không có "restriction".
- **Sửa (chỉ nhánh bệnh nhân):** `keep_qualities` thêm lại các cụm phẩm chất mong muốn mà LLM bỏ (low-sodium, low-fat, low-sugar, high-fiber và các biến thể tiếng Việt), có ghi vào `notes`. Nhánh không có bệnh nhân giữ nguyên (hồi quy), nên vẫn có giới hạn trên.
- Test: `strip_negation` giữ low-salt/low-sodium; với pe03 ở nhánh bệnh nhân, `query_en` còn "low-sodium" dù mô hình bỏ; nhánh không có bệnh nhân không đổi.

### Sau MV3 – mục 6: lượt 2 kịch bản dị ứng và bảng gate MV3 (17/10/2026)
- **Lượt 2 (pv06):** lần chạy đầu, M1 không trả `remove_allergens`, mà câu cũng không có tín hiệu gỡ quen thuộc. Đã thêm, **chỉ cho nhánh bệnh nhân**:
  - tín hiệu gỡ "không sao", "cứ cho"…;
  - quy tắc tất định `lift_named`: tín hiệu gỡ cộng một nhóm dị ứng đang bị loại mà tin nhắn nhắc tới ("tôm" → giáp xác) thì là yêu cầu gỡ.
- Sự kiện `constraints` có thêm `record_locked`, kèm thông báo "Ràng buộc này đến từ hồ sơ bệnh nhân, không gỡ được qua tin nhắn; cần xác nhận trên giao diện". Trace M2 có `refused_removals`.
- **Route `patient_info`:** lần sinh lại từng chép nguyên khối `<patient_profile>` mà vẫn qua kiểm tra, vì mình đã cho phép cả số trong khối hồ sơ, sai quyết định. Đã sửa:
  - tập số hợp lệ chỉ gồm `facts` của nút đã đọc;
  - M7 bắt việc chép lại khối dữ liệu (`echo:prompt_block`);
  - viết lại lời nhắc khi sinh lại.
- Test hồi quy khi không có bệnh nhân: **pass** (sau mọi thay đổi trên, trừ lần sửa cuối chỉ chạm nhánh bệnh nhân).

| Kịch bản / lượt | Route | CVR_raw | CVR_adjudicated | Chờ duyệt | Đã xác nhận | Ghi chú |
|---|---|---:|---:|---:|---:|---|
| 1 Dị ứng, lượt 1 | retrieve | 3/5 | 1/5 | 1 | 0 | R13999 bị loại tự động, R2920 = no (Thy), R8897 chờ duyệt |
| 1 Dị ứng, lượt 2 (pv06) | retrieve | 3/5 | 1/5 | 1 | 0 | (a)(b)(c)(d) đạt. Kiểm tra (b) của M7 vẫn gắn cờ vì tên món chứa "Shellfish" (dipping sauce for shellfish) |
| 2 Tăng huyết áp | retrieve | 0/5 | 0/5 | 0 | 0 | Luật mềm chất béo bão hòa có tác dụng |
| 3 CKD, súp | retrieve | 0/5 | 0/5 | 0 | 0 | Natri và protein |
| 3 CKD, câu hỏi lịch sử | patient_info | – | – | – | – | V2: 1 lần gọi. **Câu trả lời chép khối hồ sơ** (lần chạy trước khi sửa lời nhắc) |
| 3 CKD, pe02 | patient_info | – | – | – | – | **Chưa đạt** |

- Hàng duyệt `eval/labels/checker_queue.csv`: 6 phiếu. Tất cả có vẻ là bộ kiểm sai: salmon → lúa mì; mahi mahi, yogurt, Worcestershire → giáp xác; Worcestershire → lúa mì ở R31477.
- **Route `patient_info` với `qwen2.5:7b` chưa đạt yêu cầu.** Thử lại với lời nhắc mới thì câu trả lời qua kiểm tra số, nhưng vẫn **diễn giải** ("normal glucose… elevated protein in the urine"), trả lời câu tiếng Việt bằng tiếng Anh, và kiểm tra số còn để lọt số nguyên nhỏ trùng ngẫu nhiên.

### Cần Thy quyết định (trước khi đóng gate MV3)
1. **Route `patient_info`:**
   - (a) M7 thêm kiểm tra từ diễn giải (normal/abnormal/elevated/high/low/bình thường/cao/thấp/tăng/giảm…);
   - (b) nếu sau một lần sinh lại vẫn sai, thay bằng câu trả lời tất định do code sinh: "Việc diễn giải cần bác sĩ" kèm danh sách giá trị, đơn vị, ngày, `[H:…]` của nút đã đọc;
   - hoặc cả hai. Mình đề xuất cả hai.
2. **Kiểm tra (b) của M7 bắt nhầm tên món** ("…for Shellfish"): có loại tên món `[R…]` ra khỏi phép so không.
3. Duyệt 6 phiếu trong `checker_queue.csv`. Nhãn R2920 áp theo từng công thức; có muốn một nhãn theo chuỗi bằng chứng (ví dụ "Worcestershire sauce" với `allergen:wheat`) áp cho mọi công thức không.
4. Nhãn golden pv10 (`intent: "chat"`).

### Sau MV3 – vòng 2 (Thy, 17/10/2026)
1. **Route `patient_info`:** làm cả hai phương án, kèm chỉnh sửa của Thy:
   - M7 kiểm tra từ diễn giải (normal/elevated/high/low/bình thường/cao/thấp/tăng/giảm…) **chỉ trong câu có con số**, sau khi **che tên bệnh lấy từ hồ sơ** (và các tên tiếng Việt tương ứng: tăng huyết áp, tiểu đường…).
   - Nếu sinh lại vẫn sai: thay bằng `values_answer` do code sinh ("Việc diễn giải kết quả cần bác sĩ. Hồ sơ ghi:" kèm giá trị, đơn vị, ngày, `[H:…]`, nút mới nhất trước).
   - **Mỗi lần dùng câu trả lời do code sinh, trace ghi một dòng `fallback`** (kèm cờ của câu trả lời của mô hình); sự kiện `done` có `fallback`. Tỉ lệ này sẽ đưa vào báo cáo.
2. **Tên món:** che nguyên văn tiêu đề các công thức được trích dẫn và các chuỗi `[R…]` (cả `R123` không có ngoặc) trước khi kiểm tra văn bản. Không bỏ cả câu.
3. **6 phiếu trong hàng duyệt:** Thy duyệt cả 6 = không vi phạm (R8897 lúa mì; R7750, R11169, R31477, R10006 giáp xác; R31477 lúa mì). Đã ghi vào `eval/labels/checker_adjudication.csv` (tổng 7 nhãn).
4. **pv10:** `intent = out_of_scope`.
- Test: thêm 4 test (diễn giải, che tên món, `values_answer`, thay câu trả lời kèm dòng trace). `pytest` nhanh: 466 pass.

### Bảng gate MV3 sau vòng 2 (17/10/2026; `eval/mv3_demo.json`, CVR tính lại theo đủ 7 nhãn)
Test chậm: hồi quy khi không có bệnh nhân **pass**; 3 kịch bản demo **pass**.

| Kịch bản / lượt | Route | CVR_raw | CVR_adjudicated | Chờ duyệt | Ghi chú |
|---|---|---:|---:|---:|---|
| Hồi quy không có `patient_id` | – | – | – | – | Trùng mốc ở cả 9 lượt |
| 1 Dị ứng, lượt 1 | retrieve | 3/5 | 0/5 | 0 | |
| 1 Dị ứng, lượt 2 (pv06) | retrieve | 4/5 | 0/5 | 0 | (a)(b)(c)(d) đạt. **Câu trả lời cuối vẫn có "Bệnh nhân nên thêm tôm để tăng protein"**: M7 bắt được (`text:allergen:crustacean_shellfish`), nhưng sinh lại vẫn sai và câu trả lời vẫn được gửi (`verified = false`) |
| 2 Tăng huyết áp | retrieve | 0/5 | 0/5 | 0 | |
| 3 CKD, súp | retrieve | 0/5 | 0/5 | 0 | |
| 3 CKD, câu hỏi lịch sử | patient_info | – | – | – | Qua kiểm tra (không có số), nhưng trả lời câu tiếng Việt bằng tiếng Anh và chung chung |
| 3 CKD, pe02 | patient_info | – | – | – | Qua kiểm tra: có câu "Interpretation of the results requires a medical professional"; không cần `fallback` |

- Tỉ lệ `fallback` (câu trả lời do code sinh) trong demo: 0/2 lượt `patient_info`.
- **Hạn chế còn lại của kiểm tra số:** "84 lab panels, 33 …" qua được vì trùng ngẫu nhiên với một giá trị trong `facts`. Số nguyên nhỏ rất dễ khớp tình cờ.

### Cần Thy quyết định
1. **Câu trả lời công thức (route `retrieve`) vẫn sai sau khi sinh lại, ở kiểm tra (b) (gợi ý thứ phải tránh):** hiện vẫn được gửi đi. Đề xuất:
   - xóa tất định các câu có cụm bị gắn cờ, ghi trace `fallback = drop_sentences`;
   - nếu không còn câu nào, trả về danh sách tên món kèm cảnh báo.
2. Ngôn ngữ trả lời của route `patient_info` (câu tiếng Việt trả lời bằng tiếng Anh): có thêm kiểm tra tất định cho ngôn ngữ không.

### Sau MV3 – vòng 3 (Thy, 17/10/2026)
1. **`drop_sentences` kèm ba điều kiện:**
   - Câu trả lời công thức vẫn sai sau khi sinh lại → xóa các câu gợi ý thứ phải tránh, rồi chạy lại M7 trên phần còn lại. Còn vi phạm, hoặc không còn trích dẫn `[R…]` hợp lệ → `recipes_answer` (danh sách món do code sinh kèm cảnh báo). Trace ghi `fallback` với `kind = drop_sentences` hoặc `recipes_answer`.
   - Kiểm tra lời văn bắt cả từ chỉ nhóm: alias chế độ `all` có sẵn ("hải sản"), cộng `GROUP_WORDS` riêng của M7 ("seafood", "shellfish", "đồ biển"). "đồ biển" **chưa có trong `vi_alias.csv`**; mình không thêm vào từ điển của bộ gắn thẻ.
   - M6 (`PATIENT_RULES`): khi yêu cầu của người dùng mâu thuẫn với hồ sơ, giải thích ngắn vì sao không đáp ứng được, và không gợi ý thứ đó dưới bất kỳ hình thức nào.
2. **Ngôn ngữ ở route `patient_info`:** kiểm tra tất định (`lang:vi` / `lang:en`), sai thì sinh lại rồi `values_answer`.
3. **Số kèm đơn vị:** số đi kèm một đơn vị có trong hồ sơ phải khớp giá trị có cùng đơn vị. Số không có đơn vị phải là phần ngày tháng, năm của nút, số nằm trong tên xét nghiệm, hoặc số đếm tính từ cây (số bảng, số lần khám, số chỉ số, số theo từng tên). Đơn vị chứa chữ số ("10\*3/uL") được thay bằng nhãn trước khi quét.
- `values_answer` đưa kết quả mới nhất lên trước, cả trong từng nút. Sửa sau lần chạy demo cuối, nên trong `eval/mv3_demo.json` thứ tự vẫn là cũ trước.
- `pytest` nhanh: 472 pass. Test chậm: hồi quy **pass**, demo **pass**.

### Bảng gate MV3 (lần chạy cuối, `eval/mv3_demo.json`)
| Kịch bản / lượt | Route | CVR_raw | CVR_adjudicated | Chờ duyệt | Câu trả lời do code sinh | Ghi chú |
|---|---|---:|---:|---:|---|---|
| Hồi quy không có `patient_id` | – | – | – | – | – | Trùng mốc ở cả 9 lượt |
| 1 Dị ứng, lượt 1 | retrieve | 3/5 | 0/5 | 0 | không | |
| 1 Dị ứng, lượt 2 (pv06) | retrieve | 3/5 | 0/5 | 0 | không | (a)(b)(c)(d) đạt; không còn gợi ý tôm; câu trả lời chưa giải thích vì sao không gợi ý món tôm |
| 2 Tăng huyết áp | retrieve | 0/5 | 0/5 | 0 | không | |
| 3 CKD, súp | retrieve | 0/5 | 0/5 | 0 | không | |
| 3 CKD, câu hỏi lịch sử | patient_info | – | – | – | **có** (`values_answer`) | Lần đầu diễn giải ("bình thường", "giảm"…), lần sinh lại sai ngôn ngữ |
| 3 CKD, pe02 | patient_info | – | – | – | **có** (`values_answer`) | Lần đầu bịa 10 con số và khoảng tham chiếu, có "normal"; lần sinh lại sai ngôn ngữ |

- **Tỉ lệ câu trả lời do code sinh trong demo:** route `patient_info` 2/2; route `retrieve` 0/4.

### Hạn chế (ghi vào mục 4.6 của báo cáo)
- Kiểm tra số còn lọt hai trường hợp:
  - (1) số không có đơn vị trùng tình cờ một số đếm, phần ngày tháng hoặc số trong tên xét nghiệm;
  - (2) số đúng đơn vị nhưng thuộc chỉ số khác (ghép theo đơn vị, chưa ghép theo tên chỉ số).
- Từ diễn giải được kiểm bằng danh sách từ khóa, chỉ trong câu có số. Câu không có số mà diễn giải thì không bị bắt.
- Kiểm tra ngôn ngữ dựa trên dấu tiếng Việt và từ phổ biến. Câu trả lời tiếng Anh có chép nguyên một cảnh báo tiếng Việt sẽ bị coi là tiếng Việt.
- `qwen2.5:7b` trên CPU gần như luôn cần câu trả lời do code sinh ở route `patient_info`.

---

## MV4 – Đánh giá nhánh hồ sơ bệnh nhân (17–18/10/2026) · 🚦 đã duyệt 18/10/2026

### Quyết định đầu MV4 (Thy, 17/10/2026)
- Viết code và chạy thử (khoảng 10 câu) trên CPU máy này. **Lần chạy đầy đủ do Thy chạy trên máy GPU** (`docs/run_mv4_gpu.md`).
- **Không có câu do người viết.** Câu hỏi sinh từ mẫu câu rồi diễn đạt lại bằng `llama3.1:8b`; ghi là hạn chế.
- Bốn mốc con có điểm dừng: MV4a (sinh thêm bệnh nhân), MV4b (P8 và bộ câu, đóng băng sau khi Thy duyệt), MV4c (baseline, narrative, `eval_patient.py`, chạy thử), MV4d (chạy đầy đủ trên GPU).
- **Cấu hình Synthea:** commit `d9d07a6` sinh bộ mẫu bằng `generate_samples.sh` (`./run_synthea -p 100 --exporter.ccda.export=true …`, cấu hình mặc định, không seed; CI dùng Java 17). Bộ sinh thêm giữ cấu hình đó và chỉ thêm seed 42, độ tuổi 40–90, `generate.only_alive_patients=true`.

### MV4a – Sinh thêm bệnh nhân Synthea (17/10/2026) · 🚦 chờ duyệt
- Cài JDK 17 (OpenJDK 17.0.20.1, Microsoft). Synthea ở commit `d9d07a6` (lấy đúng snapshot commit đó vào `../synthea`, ngoài repo). Build Gradle thành công.
- Lệnh (ghi trong `data/sources.json`):
  ```
  ./run_synthea -s 42 -cs 42 -p 1000 -a 40-90 --exporter.ccda.export=true --exporter.fhir.export=false --generate.only_alive_patients=true
  ```
  Synthea báo `total=1000, alive=1000, dead=0`, nhưng **chỉ có 983 file C-CDA** (không trùng mã bệnh nhân). 17 bản ghi không được bộ xuất C-CDA ghi ra; chưa rõ lý do.
- `scripts/patient_select.py`: tầng theo đúng mã của `condition_nutrient.csv`, cộng đa bệnh và dị ứng thực phẩm; chọn có seed 42, chỉ lấy người làm đầy tầng còn thiếu (`eval/patient_selection.json`).
  - Người còn sống trong bộ mẫu: tăng huyết áp 18, dị ứng thực phẩm 11, tiểu đường 5, đa bệnh 5, CKD 4.
  - Trong 983 người sinh thêm: tiểu đường 243, đa bệnh 222, tăng huyết áp 390, CKD 175, dị ứng thực phẩm 100. Đây là nhóm 40–90 tuổi, đa bệnh nhiều.
  - **Chỉ cần 12 người sinh thêm** là đủ (phần lớn vừa tiểu đường vừa CKD). Sau khi bổ sung: tiểu đường 16, đa bệnh 16, CKD 15, tăng huyết áp 28, dị ứng thực phẩm 12.
- **So cấu trúc** 12 file đã chọn với 108 file mẫu: không có sai khác (cùng các section; SNOMED cho dị ứng và bệnh, RxNorm cho thuốc). Khác về nội dung: 12 người sinh thêm có 5.320 entry thuốc, trong khi 108 người mẫu có 3.850.
- `patient_ingest.py load`: 120 bệnh nhân (108 mẫu, 12 sinh thêm), 0 lỗi parse. Cây: 2.959 nút (376 nút ngữ cảnh ở nguồn sinh thêm). `profiles`: 112 người còn sống, 7 người dưới 50% kho (đều do dị ứng), thấp nhất 18,4%.
- Test: 2 test mới (`tests/patient/test_patient_select.py`). `pytest` nhanh: 474 pass.

**Cần Thy xem:**
- 12 người sinh thêm (nhóm đa bệnh lớn tuổi) so với 100 người mẫu. Bảng độ nhạy chỉ trên `sample` vẫn giữ như đã quyết.
- Có cần tìm hiểu 17 bản ghi không được xuất C-CDA không.

### MV4b – Mẫu P8 và bộ câu hỏi (17/10/2026) · 🚦 đã duyệt, đóng băng 18/10/2026
- `scripts/patient_sample.py` → `eval/patient/sample.json`: **100 bệnh nhân** còn sống (88 mẫu, 12 sinh thêm). Lấy toàn bộ 42 người có ràng buộc, cộng 58/70 người không ràng buộc (seed 42).
  - Tầng chính: đa bệnh 16, tăng huyết áp 15, dị ứng thực phẩm 10, tiểu đường 1, không ràng buộc 58.
  - Theo tầng (một người có thể ở nhiều tầng): tiểu đường 16, CKD 15, đa bệnh 16, tăng huyết áp 28, dị ứng thực phẩm 12.
- `scripts/make_patient_queries.py` → `eval/patient/queries.jsonl`: **300 câu**, mỗi bệnh nhân 1 câu cho mỗi loại (không nêu ràng buộc / thêm ràng buộc: chay 34, dưới 30 phút 21, không có một nguyên liệu 45 / cần ngữ cảnh). 151 câu tiếng Việt, 149 câu tiếng Anh.
  - **Không có câu do người viết.** Câu sinh từ mẫu, diễn đạt lại bằng `llama3.1:8b` theo một "giọng" chọn theo seed.
  - Bộ lọc diễn đạt: bỏ bản diễn đạt làm mất con số, nguyên liệu, từ "chay", nhắc tới bệnh nhân hoặc đổi ngôn ngữ; và bỏ bản **thêm** từ chỉ chế độ ăn, nhóm dị ứng, thời gian, con số, danh sách hoặc **một nguyên liệu bất kỳ trong từ điển** mà câu mẫu không có.
  - **Lần chạy đầu không dùng được:** mô hình thêm "vegetarian" vào câu không có ràng buộc, bịa cả công thức có hạt điều, và chỉ có 66 câu khác nhau. Đã sửa như trên.
  - Kết quả: **208/300** bản diễn đạt được giữ, 92 câu dùng nguyên câu mẫu; 132 câu khác nhau. Còn vài câu trôi nghĩa nhẹ mà bộ lọc không bắt được (ví dụ pq297 "lần khám gần nhất là khám gì?" thành "khám bệnh nhân lần nào gần đây?"; pq220 thêm "healthy").
- **V7:** câu chặt nhất vẫn còn 3.584 công thức thỏa; 0 câu không trả lời được.
- `eval/patient/gold.jsonl`: đáp án lấy tự động từ entry có mã (chất dị ứng thực phẩm, bệnh, thuốc đang dùng; nút ngữ cảnh mới nhất cho câu loại 3).
- `eval/patient/manual_check.csv`: 20 bệnh nhân (có đủ mọi tầng chính) để **Thy kiểm tay** đáp án với file gốc. Chưa điền.
- `scripts/freeze_patient_set.py` và test kiểm sha256 đã sẵn sàng, **chưa chạy**.
- Test: 7 test mới. `pytest` nhanh pass.

**Cần Thy:**
1. Duyệt bộ câu: đọc `eval/patient/queries.jsonl`, đặc biệt các câu `paraphrase_ok = true` trôi nghĩa. Có thể chỉ định qid nào cần dùng lại câu mẫu.
2. Điền `eval/patient/manual_check.csv` (các cột `*_ok`, `note`).
3. Xong 1 và 2 thì chạy (hoặc bảo mình chạy) `scripts/freeze_patient_set.py --approved-by Thy`.

**Gate MV4b (Thy, 18/10/2026):**
- `eval/patient/manual_check.csv`: Thy đối chiếu 20/20 bệnh nhân bằng script độc lập `eval/patient/verify_manual_check.py` (không import `api/patient`) cộng soát tay. Cả ba cột (dị ứng thực phẩm, bệnh, thuốc) đều `ok` ở 20/20.
- Lưu ý trong ghi chú của Thy, mình đã kiểm:
  - 3 bệnh nhân sinh thêm không có mã "Diabetes mellitus type 2", chỉ có biến chứng "due to type 2 diabetes" (hoặc "Prediabetes (finding)"). **Luật ADA (chất xơ, luật mềm) vẫn được áp** cho cả 3, vì các mã biến chứng nằm trong luật T2D từ MV2 (`eval/patient_profiles.json`).
  - CKD giai đoạn 1, 2, 3 cùng active: luật protein áp vì có mã giai đoạn 3.
  - Thuốc dùng một lần có ngày kết thúc `UNK` (Alteplase, fentanyl…) được tính "đang dùng" theo quy tắc 2.2 của đặc tả. Đây là hạn chế của quy tắc (ảnh hưởng độ đo trích thuốc, không ảnh hưởng ràng buộc). Ghi vào mục 4.6.
  - Norethindrone không có luật trong `drug_food.csv`, nên không vào prompt (`prompt_view`).
- **Đóng băng** `eval/patient/queries.jsonl` và `gold.jsonl` (`eval/patient/frozen.json`; queries `efac0618…`, gold `4e2fbf8e…`). `make_patient_queries.py` từ chối chạy lại; test kiểm sha256.

### MV4c – Baseline, chế độ narrative, `eval_patient.py`, chạy thử (18/10/2026) · đã duyệt

**Quyết định (Thy, 18/10/2026):** lần chạy đầy đủ chạy trên máy này (RTX 4060 Laptop, 8 GB), thay cho "máy GPU khác". Máy này có GPU và Ollama đã chạy trên GPU; nhận định "máy CPU" lúc lên kế hoạch là sai.

**Đã làm**
- `api/patient/narrative.py`: chế độ đầu vào narrative. Mỗi section của bảng `<text>` là một nút (`narrative.*`). Không có mã hay `statusCode`. Các dòng P7 bị bỏ (dựa vào cột Code) trước khi văn bản đến mô hình. Chế độ này chỉ dùng khi đánh giá.
- `api/patient/baselines.py`:
  - qwen trích ràng buộc theo JSON schema (dị ứng thực phẩm, bệnh, thuốc đang dùng). Văn bản dài được đọc từng phần 12.000 ký tự rồi gộp kết quả. Mô tả được tra mã qua một từ điển lấy từ mọi file hồ sơ.
  - P-Vector: chunk 8 dòng, embed bằng nomic, lấy top 6 theo câu hỏi.
  - P-Vectorless-Fixed: mô hình chọn trong mọi nút. Prompt ghi rõ nút không được chọn thì không được đọc.
- Orchestrator chạy đủ 5 preset × 2 chế độ đầu vào. P-Direct trên narrative = N/A. S-Profile không đọc hồ sơ nên chỉ chạy ở chế độ coded và dùng chung kết quả cho bảng narrative. Tổng **2.400 lượt** cho lần chạy đầy đủ.
- `scripts/eval_patient.py`:
  - hai lệnh `run` (có `--resume`, dùng lại thiết lập trong `settings.json`) và `score`; tự kiểm bộ câu đã đóng băng;
  - độ đo: trích P/R/F1 và số ca dị ứng bỏ sót; chọn nút đúng (chỉ chế độ coded); chi phí; CVR@5 và Safe@5 theo dị ứng, dinh dưỡng và hội thoại (raw và adjudicated); [H:]; câu trả lời do code sinh;
  - bootstrap và Wilcoxon theo bệnh nhân, Holm trong từng họ; bảng độ nhạy chỉ trên `sample`;
  - lần chạy có `--limit` ghi hàng duyệt vào thư mục run, không ghi vào `eval/labels/`.
- `docs/run_mv4_gpu.md`: hướng dẫn chạy đầy đủ.

**Lỗi tìm thấy khi chạy thử, đã sửa** (mục 2, 5, 6 và 7 sửa code MV3; Thy duyệt 18/10)
1. Bộ kiểm LLM, khi được hỏi từng nguyên liệu nhuyễn thể một, đọc "chicken broth" thành "clam juice". Nguyên liệu có tên giờ được chấm bằng so khớp nguyên từ trên dòng nguyên liệu thô.
2. **Ollama giữ tối đa nửa `num_ctx` cho prompt và bỏ phần đầu (system prompt) mà không báo lỗi.** Log ghi 46 prompt bị cắt, lớn nhất 178.004 token. Trong 100 bệnh nhân của P8 có 28 người vượt mức ở route `patient_info` (coded) và 14 người vượt mức ở bước trích narrative. Cách sửa:
   - `llm.py` từ chối prompt chắc chắn quá dài, và báo `PromptTooLong` khi `prompt_eval_count` chạm nửa `num_ctx`;
   - M6 `patient_info` lấy mục mới nhất trước trong ngân sách 11.000 ký tự, `num_ctx` 16384, ghi `older_entries_not_shown`, và trace ghi `record_omitted`;
   - bước trích đọc từng phần;
   - V1c lấy mục mới nhất trước trong 12.000 ký tự (16k);
   - V2 dùng `num_ctx` 8192 (mục lục lớn nhất ~2.300 token);
   - embed không cho cắt (`truncate: false`).
3. Ollama từ chối 450 lời gọi tokenize song song khi embed. Giờ embed theo lô 32.
4. `--resume` ban đầu lấy `--limit` từ dòng lệnh. Đã dừng kịp, không có lượt thừa.
5. **V2 không biết ngày của hồ sơ**, nên với qwen thì năm 2026 là tương lai, và chọn nút đúng 0/5. Prompt giờ ghi ngày của hồ sơ; kết quả lên 4/5 trong lần chạy thử cuối.
6. Reranker trên CPU mất khoảng 12 giây mỗi lượt. Giờ dùng torch `2.11.0+cu128`, 50 cặp mất 0,16 giây. Test hồi quy không đổi thứ tự công thức.

**Lần chạy thử cuối** (`eval/runs/20261018-123903/patient`; 10 câu, 80 lượt, 11 phút; nhiều lời gọi đã có cache):

| | Kết quả |
|---|---|
| Trích, coded | P-Direct và P-Vectorless 100%; P-Vectorless-Fixed bệnh F1 3%, bỏ sót 1/2 dị ứng; P-Vector bỏ sót 1/2 dị ứng |
| Trích, narrative | P-Vectorless thuốc F1 90%, bệnh 49%, bỏ sót 1/2 dị ứng; P-Vector và P-Vectorless-Fixed bỏ sót 2/2 |
| Safe@5 dinh dưỡng | 100% với mọi preset có đọc hồ sơ; 40% với S-Profile |
| Safe@5 dị ứng | 100% với mọi preset (4 câu; món được gợi ý tình cờ không chứa chất gây dị ứng) |
| Chọn nút đúng, coded | P-Vectorless 4/5, P-Vectorless-Fixed 5/5, P-Vector 5/5, P-Direct 0/5 (không đọc nút ngữ cảnh) |

Ước tính cho 2.400 lượt khoảng 5,5 giờ nếu có cache; chạy không có cache thì khoảng 6–8 giờ.

**Còn mở (chờ Thy):**
- M7 ở route `patient_info` chuyển sang câu trả lời do code sinh quá nhiều: 5/10 ở P-Vectorless coded. Có hai nguyên nhân:
  - (a) `VI_WORDS` có chữ "the" (tức "thế"), nên câu trả lời tiếng Anh bị coi là tiếng Việt;
  - (b) số liệu thô nhiều chữ số thập phân (`7.45597543353983`) mà mô hình làm tròn thành `7.46`, nên bị coi là số lạ.
- **Quyết định (Thy, 18/10/2026): không sửa (a) và (b).** Ghi vào phần hạn chế của báo cáo:
  - tỉ lệ câu trả lời do code sinh ở route `patient_info` bị đẩy lên vì báo động giả. Câu trả lời tiếng Anh có hai chữ "the" bị coi là tiếng Việt, và số làm tròn từ số liệu thô bị coi là số lạ;
  - khi đó câu trả lời là `values_answer`, liệt kê đúng giá trị của hồ sơ, nên an toàn, chỉ kém tự nhiên;
  - mỗi lượt như vậy có `fallback` và cờ M7 trong `turns.jsonl`, nên báo cáo tách được số do lỗi (a) (`lang:*`) và (b) (`number:*`).

### MV4d – Lần chạy đầy đủ (18/10/2026) · đã duyệt
- **V1c:** 2.359 tóm tắt LLM cho các nút ngữ cảnh của 120 bệnh nhân, 33 phút. Mục lục của V2 giờ dùng tóm tắt này; các lần chạy thử ở MV4c dùng tóm tắt template.
- **Run** `eval/runs/20261018-132948/patient` (đã commit):
  - 2.400 lượt trên RTX 4060 Laptop, từ 13:29 đến 21:58 (đã gồm bước chấm);
  - 1.583 lượt đầu chạy với code `b0fd1da`. Lần chạy dừng ở pq084: một câu trả lời M6 lặp vô hạn (Ollama chạy với context shift), và bộ chặn prompt bắt được ở lần sinh lại;
  - Thy duyệt giới hạn **2.048 token sinh ra cho M6** (`a209290`; không lượt nào trong 1.583 lượt trước vượt 1.231 token), rồi chạy tiếp 817 lượt bằng `--resume`. `settings.json` ghi cả hai commit. Không câu trả lời nào chạm giới hạn.
- **Số liệu chính** (từ `table.md`; dị ứng tính trên 74 câu của 37 bệnh nhân có ràng buộc dị ứng hoặc nguyên liệu trong hồ sơ; phiếu pending đang tính là vi phạm):

| Đầu vào | Preset | Recall dị ứng (bỏ sót ca/BN) | Safe@5 dị ứng adj | Safe@5 dinh dưỡng | Chọn nút đúng | Trả lời do code |
|---|---|---|---|---|---|---|
| coded | P-Direct | 100% (0/0) | 86% | 100% | 0% | 14% |
| coded | **P-Vectorless** | 100% (0/0) | 86% | 100% | 78% | 8% |
| coded | P-Vectorless-Fixed | 35% (41/12) | 81% | 96% | 87% | 8% |
| coded | P-Vector | 14% (54/11) | 78% | 98% | 84% | 8% |
| coded | S-Profile | – | 77% | 36% | – | 0% |
| narrative | P-Vectorless | 86% (9/3) | 86% | 100% | – | 12% |
| narrative | P-Vectorless-Fixed | 14% (54/12) | 81% | 94% | – | 11% |
| narrative | P-Vector | 18% (52/12) | 81% | 94% | – | 9% |

- **So sánh theo bệnh nhân** (bootstrap, Holm; kèm Wilcoxon, Holm):
  - recall dị ứng, P-Vectorless hơn P-Vectorless-Fixed +0,69 và hơn P-Vector +0,82 ở coded, +0,69 ở narrative; p < 0,005 ở cả hai cách tính;
  - Safe@5 dinh dưỡng hơn S-Profile +0,64 (p < 0,001);
  - Safe@5 dinh dưỡng hơn P-Vectorless-Fixed +0,04 ở coded: p bootstrap 0,015, nhưng p Wilcoxon 0,78. Phần lớn bệnh nhân có chênh lệch bằng 0, và Wilcoxon (`zsplit`) xử lý số 0 rất thận trọng; báo cáo nêu cả hai;
  - Safe@5 dị ứng: P-Vectorless hơn các baseline +0,05 đến +0,10, nhưng chưa có ý nghĩa sau Holm (37 bệnh nhân; còn 89 phiếu pending).
- **Chọn nút đúng:** P-Vectorless 78%, thấp hơn P-Vectorless-Fixed (87%, p bootstrap 0,016) vì chỉ chọn tối đa 3 nút ngữ cảnh. Nhưng P-Vectorless-Fixed đổi lại recall dị ứng chỉ 35%.
- **[H:]:** mọi trích dẫn đều trỏ vào nút có thật. Phần "không đọc" là các trích dẫn tới nút gốc `patient:<id>`.
- **Chi phí** (lượt đầu của bệnh nhân): coded P-Vectorless 0 lời gọi LLM ở V1–V3; narrative P-Vectorless 2,1 lời gọi, đọc ~19.500 ký tự, V3 mất 16 giây; sang các lượt sau thì gần như toàn cache hit.
- **Bộ kiểm độc lập:** 227 công thức. 15 phiếu "yes" bị loại vì bằng chứng do chính bộ kiểm đánh dấu là không hợp lệ; **89 phiếu đưa vào hàng duyệt mù** `eval/labels/checker_queue.csv`.

**Cần Thy:** gán nhãn 89 phiếu vào `eval/labels/checker_adjudication.csv` (theo `docs/annotation_guide.md` mục 8). Sau đó chạy `uv run scripts/eval_patient.py score eval/runs/20261018-132948/patient` để có CVR adjudicated cuối cùng, rồi đến gate MV4.

**Sau khi Thy gán nhãn (18/10/2026):**
- `eval/labels/checker_adjudication.csv`: 89 nhãn mới. Ban đầu cả 89 ghi `reviewer = claude-draft`; Thy đã duyệt và đổi thành `Thy`. 7 nhãn cũ giữ nguyên giá trị (Excel đổi định dạng ngày thành `10/18/2026`).
  - Kết quả 89 phiếu: 48 vi phạm thật, 41 không vi phạm; 15 phiếu đã bị loại tự động vì bằng chứng do chính bộ kiểm đánh dấu là không hợp lệ.
- **Sửa bộ chấm** (áp như nhau cho mọi preset): phép so khớp tên nguyên liệu coi "oyster mushrooms" (nấm sò) là "oyster" (hàu), 7 lần. Rà toàn bộ các dòng khớp thì đây là loại báo động giả duy nhất. `FALSE_FRIENDS` giờ xóa cụm này trước khi so khớp.
- **Kết quả adjudicated cuối cùng** (`eval_patient.py score`; 74 câu của 37 bệnh nhân có ràng buộc dị ứng hoặc nguyên liệu trong hồ sơ):

| Đầu vào | Preset | Safe@5 dị ứng adj | CVR@5 dị ứng raw / adj |
|---|---|---|---|
| coded | P-Direct | 99% (73/74) | 5,7% / 0,3% |
| coded | **P-Vectorless** | **99% (73/74)** | 5,7% / 0,3% |
| coded | P-Vectorless-Fixed | 91% | 8,4% / 3,5% |
| coded | P-Vector | 82% | 10,5% / 5,9% |
| coded | S-Profile | 81% | 11,4% / 6,2% |
| narrative | P-Vectorless | 97% | 5,7% / 0,5% |
| narrative | P-Vectorless-Fixed | 89% | 9,2% / 4,3% |
| narrative | P-Vector | 86% | 8,6% / 4,1% |

- **So sánh Safe@5 dị ứng theo bệnh nhân** (37 bệnh nhân; bootstrap, Holm):
  - coded: P-Vectorless hơn P-Vectorless-Fixed +0,08 (p 0,017), hơn P-Vector +0,16 (p 0,001), hơn S-Profile +0,18 (p < 0,001);
  - narrative: hơn P-Vector +0,11 (p 0,011), hơn S-Profile +0,16 (p < 0,001); so với P-Vectorless-Fixed +0,08 (p 0,066);
  - Wilcoxon (Holm) cho p từ 0,07 đến 0,30, vì phần lớn bệnh nhân có chênh lệch bằng 0;
  - bảng độ nhạy chỉ trên `sample` (26 bệnh nhân) cùng chiều, và chênh lệch lớn hơn.
- **Vi phạm dị ứng duy nhất còn lại ở P-Vectorless** (cả P-Direct): pq103, R21159. Dòng "dry-roasted, unsalted peanuts" không được bộ gắn thẻ gắn `peanut` (món này chỉ có thẻ `sesame`). Đây là lỗi bỏ sót của bộ gắn thẻ ở M2, và mọi preset lọc theo thẻ đều chịu chung. Ghi vào phần hạn chế.

**Gate MV4 (Thy, 18/10/2026): duyệt.** Số liệu chính thức là run `eval/runs/20261018-132948/patient` sau khi adjudicate (`b1f0c1a`). Bước tiếp theo là MV5, bắt đầu bằng plan mode.

## MV5 – Giao nhánh hồ sơ cho M4 (18/10/2026) · 🚦 chờ duyệt

**Phạm vi (Thy chọn, 18/10):** ghi hợp đồng, và code phần riêng của hồ sơ có test. Để lại cho M4: `POST /chat` (SSE), API phiên, route `PATCH`, UI.

**Đã làm**
- **Endpoint đọc** (`api/patient_api.py`, gắn vào `api/main.py`; `get_conn` chuyển sang `api/deps.py`):
  - `GET /patients` (lọc `alive_only`, có tóm tắt ràng buộc), `GET /patients/{id}/tree`, `GET /patients/{id}/profile`;
  - chỉ trả prompt view (allow-list, ADR-0006), không có `entry_id`, không có tên; 404 khi không có bệnh nhân, 409 khi đã mất.
- **Xác nhận gỡ ràng buộc hồ sơ** (ADR-0008, *proposed*):
  - migration 009 (bảng `session_record_lift`, đã áp);
  - `Assistant.lift_record_constraint(session, constraint_id, confirm, reason)` cho route PATCH; cần `confirm=true` và id phải thuộc hồ sơ;
  - mỗi lượt dùng hồ sơ hiệu lực `without(profile, lifted)` ở M2, M4, M6 và M7; sự kiện `patient_profile` có thêm `lifted`;
  - tin nhắn chat vẫn không gỡ được ràng buộc hồ sơ.
- **Hợp đồng cho M4:** `docs/plan/A3_ke_hoach_build.md` mục 6.5, viết lại.
  - Thứ tự sự kiện SSE, và đủ các trường của `patient_profile`, `constraints` (`record_locked`), `recipes` (`nutrients`), `done` (`flags`, `fallback`, `done_reason`).
  - Ba endpoint, có ví dụ từ bệnh nhân fixture.
  - `PATCH /chat/{session}/constraints/{constraint_id}`: dạng id, mã lỗi, gỡ theo nhóm bằng chứng.
  - Gợi ý hiển thị (chip khóa, `record_locked`, `[H:]`, `fallback`).
- **Test:**
  - 5 test API (allow-list, không có `entry_id`, 404 và 409, không có tên);
  - 3 test cho việc gỡ (gỡ có xác nhận thì lượt sau không còn lọc và khối M6 không còn nhắc; từ chối khi thiếu `confirm`, khi id không thuộc hồ sơ, khi phiên không có bệnh nhân; `without` là hàm thuần);
  - kết quả: 524 test nhanh pass; test hồi quy cho nhánh không có bệnh nhân không đổi.

**Cần Thy:** duyệt hợp đồng ở mục 6.5 và ADR-0008.

**Sau góp ý của Thy về gom nhóm (18/10/2026):**
- **Id nhóm** `record:allergy/<mã SNOMED của chất>`: mọi ràng buộc mà một dòng dị ứng sinh ra (`mapping.record_groups`, suy từ `entry_id` của bằng chứng). Ví dụ bệnh nhân fixture: hải sản có vỏ 21 thành viên, lúa mì 1.
- **Gỡ nhóm** chạy trong một transaction và ghi một dòng có `members` (migration 010, đã áp; bảng còn trống trước đó).
  - Thành viên mà một dòng dị ứng khác cũng sinh ra được **giữ** cho tới khi nhóm kia cũng được gỡ, và trả về trong `kept`. Trên 112 bệnh nhân còn sống có 12 ràng buộc như vậy.
- **Gỡ từng mục vẫn giữ nguyên**, ví dụ "chỉ dị ứng tôm, ăn được nghêu". Ràng buộc dinh dưỡng chỉ gỡ từng mục.
- `patient_profile` và `GET /patients/{id}/profile` có thêm `groups`. Hợp đồng 6.5.3, 6.5.4 và ADR-0008 đã cập nhật.
- Test: thêm 5 test (gỡ nhóm một dòng; gỡ riêng một thành viên; thành viên dùng chung giữ tới khi gỡ cả hai nhóm; nhóm không tồn tại; API có `groups`). Kết quả: 529 test nhanh pass.
