---
status: accepted (gate M0, 14/10/2026)
---

# Lọc ràng buộc bằng cột mảng `pdb.literal` và `pdb.term_set` ngay trong index ParadeDB

A3 cần loại công thức theo nhóm dị ứng và theo nguyên liệu bị loại trừ **trước khi xếp hạng**, cho cả BM25 lẫn dense, theo cùng nguyên tắc với ADR-0001: mọi filter phải chạy bên trong `chunk_search_idx`. Spike M0 (`scripts/spike_array_filter.py`) đo ba cách biểu diễn trên pg_search 0.25.9 (cùng image với A1), dùng hai nguồn dữ liệu:
- `synthetic`: 32.719 công thức, vector ngẫu nhiên.
- `real`: 166.438 chunk `semantic` với embedding thật, restore từ `pg_dump` của A1.

Thẻ dùng trong spike là regex thô, chỉ để bộ lọc có độ chọn lọc giống thật (giữ lại từ 19% đến 97% số dòng).

**Quyết định:**
- Phi chuẩn hóa xuống `chunk` hai cột `allergens text[]` và `ingredients_norm text[]`.
- Index hai cột này với kiểu `pdb.literal`.
- Lọc bằng `NOT (allergens @@@ pdb.term_set(:excluded))`, tương tự cho `ingredients_norm`.
- Không dùng `&&`, và không dùng `=== ANY(...)`.

## Kết quả spike (nguồn `real`, LIMIT 50, 20 truy vấn × 3 lần; số gốc ở `eval/spike/array_filter_real.json`)

| Biến thể | Cách pg_search thực thi | Vi phạm | Truy vấn hụt | BM25 trùng exact | Overlap dense với exact | p50 BM25 / dense |
|---|---|---:|---:|---:|---:|---|
| Không lọc | – | – | – | 1,0 | 0,888 | 6,6 / 19,2 ms |
| A1 `NOT (allergens && …)` | `heap_filter` trong scan (đọc lại từng tuple) | 0 | 0 | 1,0 | 0,894–0,991 | 29–36 / 31–42 ms |
| **A2 `NOT (allergens @@@ pdb.term_set(…))`** | **term query native của Tantivy** | 0 | 0 | 1,0 | 0,894–0,991 | **7,5–8,2 / 21–30 ms** |
| B 9 cột `has_<allergen> = false` | term query native | 0 | 0 | 1,0 | 0,894–0,991 | 7,6–18,8 / 19–25 ms |

- Cả ba biến thể đều được đẩy vào ParadeDB Custom Scan (Top-K), không có node `Filter` nào của Postgres phía trên. Không biến thể nào trả thiếu kết quả hay lọt công thức vi phạm.
- Overlap dense có lọc **không thấp hơn** khi không lọc (0,888, do index IVF ở probe 0,02, xem ADR-0003). Như vậy filter được áp trong lúc tìm vector, không phải lọc sau rồi bị hụt.
- Tổ hợp `term_set` với `total_minutes <= 30` và `category = ANY(…)` (biến thể `D_combined`) cũng đạt cả 4 tiêu chí:
  - Không truy vấn nào có đáp án rỗng, 0 vi phạm.
  - BM25 trùng exact. Overlap dense ≥ 0,999.
  - p50 khoảng 8–9 ms với BM25 và 12–23 ms với dense.
- *Đính chính (14/10):* bản đầu của spike lọc `category` theo tên viết hoa, trong khi DB lưu dạng slug. Vì vậy đáp án của `D_combined` rỗng với mọi truy vấn, và câu kết luận trên chưa có căn cứ. Script đã được sửa và chạy lại. Giờ script cũng báo rõ những dòng có đáp án rỗng là "không đo được".

## Các phương án đã xét

- **`&&` trên `text[]`:** đúng nhưng chậm gấp khoảng 4 lần với BM25, vì pg_search chuyển nó thành `heap_filter`.
- **9 cột boolean và `ing_tokens` (phương án thay trong kế hoạch build):** cũng đạt. Nhưng sẽ thêm 9 cột vào bảng và index, mỗi nhóm dị ứng mới lại cần migration, và nguyên liệu vẫn phải dùng term query. Với BM25, cách này chậm hơn `term_set` khi lọc theo dị ứng.
- **`allergens === ANY(ARRAY[…])`:** lỗi `failed to decode CBOR` trên pg_search 0.25.9. Không dùng.
- **Lọc sau truy hồi (over-fetch):** không cần, vì lọc trước đã đúng và đủ.

## Hệ quả

- `api/filters.py` thêm điều kiện dạng `NOT (col @@@ pdb.term_set(%s::text[]))`. Danh sách rỗng thì bỏ hẳn điều kiện.
- `sql/indexes.sql` (M1) thêm `(allergens::pdb.literal)`, `(ingredients_norm::pdb.literal)` và `diet_flags`. Giá trị trong mảng phải là mã canonical **đã chuẩn hóa chữ thường**, vì `pdb.literal` khớp chính xác từng ký tự.
- **Vector truy vấn phải truyền dạng literal** (`%s::vector`, như A1 đang làm). Nếu truyền qua subquery thì planner không đẩy được `ORDER BY` xuống index, và chuyển sang quét rồi sort toàn bộ.
- Theo ADR-0001, `chunk` chỉ được build lại, không sửa tại chỗ. Khi M1 thêm cột thẻ, phải build lại phân vùng `semantic` nhưng **tái dùng embedding hiện có** (join theo `recipe_id, kind, position`). Embed lại trên máy này mất khoảng 3,9 giờ (`docs/env.md`).
- Schema `spike` (`recipe_tag`, `chunk_tag`, `chunk_real`, `probe`, `probe768`) được giữ lại trong DB A3 theo quyết định ở gate M0.
