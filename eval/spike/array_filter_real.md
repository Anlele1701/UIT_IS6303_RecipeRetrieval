# Spike lọc mảng pg_search – nguồn `real`

Sinh tự động bởi `scripts/spike_array_filter.py` lúc 2026-10-12T00:16:25. pg_search 0.25.9, probe 0.02, LIMIT 50, 20 truy vấn × 3 lần, seed 42.

## Độ chọn lọc của bộ lọc

| Bộ lọc | Số dòng còn lại | Tỉ lệ |
|---|---:|---:|
| peanut | 161,912 / 166,438 | 97.3% |
| milk | 59,589 / 166,438 | 35.8% |
| milk_egg_wheat | 31,939 / 166,438 | 19.2% |
| garlic | 109,596 / 166,438 | 65.8% |
| peanut_milk_cilantro | 52,960 / 166,438 | 31.8% |

## Kết quả theo biến thể

| Retriever | Biến thể | Bộ lọc | Pushdown | Lọc native | heap_filter | TopK | Truy vấn hụt | Vi phạm | Overlap với exact | p50 ms |
|---|---|---|---|---|---|---|---:|---:|---:|---:|
| bm25 | (không lọc) | – | | | | | | | 1.0 | 6.6 |
| bm25 | A1_overlap | peanut | có | không | có | có | 0 | 0 | 1.0 | 31.5 |
| bm25 | A2_term_set | peanut | có | có | không | có | 0 | 0 | 1.0 | 8.2 |
| bm25 | B_bool | peanut | có | có | không | có | 0 | 0 | 1.0 | 18.8 |
| bm25 | D_combined | peanut | có | có | không | có | 0 | 0 | 1.0 | 5.9 |
| bm25 | A1_overlap | milk | có | không | có | có | 0 | 0 | 1.0 | 29.3 |
| bm25 | A2_term_set | milk | có | có | không | có | 0 | 0 | 1.0 | 7.6 |
| bm25 | B_bool | milk | có | có | không | có | 0 | 0 | 1.0 | 17.8 |
| bm25 | D_combined | milk | có | có | không | có | 0 | 0 | 1.0 | 6.0 |
| bm25 | A1_overlap | milk_egg_wheat | có | không | có | có | 0 | 0 | 1.0 | 29.8 |
| bm25 | A2_term_set | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 7.5 |
| bm25 | B_bool | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 17.8 |
| bm25 | D_combined | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 6.1 |
| bm25 | A1_overlap | garlic | có | không | có | có | 0 | 0 | 1.0 | 29.1 |
| bm25 | A2_term_set | garlic | có | có | không | có | 0 | 0 | 1.0 | 7.9 |
| bm25 | B_bool | garlic | có | có | không | có | 0 | 0 | 1.0 | 7.6 |
| bm25 | D_combined | garlic | có | có | không | có | 0 | 0 | 1.0 | 5.9 |
| bm25 | A1_overlap | peanut_milk_cilantro | có | không | có | có | 0 | 0 | 1.0 | 36.3 |
| bm25 | A2_term_set | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 8.0 |
| bm25 | B_bool | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 18.6 |
| bm25 | D_combined | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 6.1 |
| dense | (không lọc) | – | | | | | | | 0.888 | 19.2 |
| dense | A1_overlap | peanut | có | không | có | có | 0 | 0 | 0.894 | 30.6 |
| dense | A2_term_set | peanut | có | có | không | có | 0 | 0 | 0.894 | 21.4 |
| dense | B_bool | peanut | có | có | không | có | 0 | 0 | 0.894 | 19.3 |
| dense | D_combined | peanut | có | có | không | có | 0 | 0 | 1.0 | 2.9 |
| dense | A1_overlap | milk | có | không | có | có | 0 | 0 | 0.968 | 34.4 |
| dense | A2_term_set | milk | có | có | không | có | 0 | 0 | 0.968 | 27.3 |
| dense | B_bool | milk | có | có | không | có | 0 | 0 | 0.968 | 22.3 |
| dense | D_combined | milk | có | có | không | có | 0 | 0 | 1.0 | 3.3 |
| dense | A1_overlap | milk_egg_wheat | có | không | có | có | 0 | 0 | 0.991 | 37.0 |
| dense | A2_term_set | milk_egg_wheat | có | có | không | có | 0 | 0 | 0.991 | 29.9 |
| dense | B_bool | milk_egg_wheat | có | có | không | có | 0 | 0 | 0.991 | 23.2 |
| dense | D_combined | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 3.3 |
| dense | A1_overlap | garlic | có | không | có | có | 0 | 0 | 0.927 | 32.8 |
| dense | A2_term_set | garlic | có | có | không | có | 0 | 0 | 0.927 | 25.0 |
| dense | B_bool | garlic | có | có | không | có | 0 | 0 | 0.927 | 25.1 |
| dense | D_combined | garlic | có | có | không | có | 0 | 0 | 1.0 | 3.2 |
| dense | A1_overlap | peanut_milk_cilantro | có | không | có | có | 0 | 0 | 0.971 | 41.8 |
| dense | A2_term_set | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 0.971 | 29.4 |
| dense | B_bool | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 0.971 | 23.5 |
| dense | D_combined | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 3.4 |

## Đánh giá theo luật quyết định (tiêu chí 1–4)

| Biến thể | Đạt | Lọc native trong index | Overlap dense thấp nhất | Lỗi |
|---|---|---|---:|---:|
| A1_overlap | có | không | 0.894 | 0 |
| A2_term_set | có | có | 0.894 | 0 |
| B_bool | có | có | 0.894 | 0 |
