# Spike lọc mảng pg_search – nguồn `synthetic`

Sinh tự động bởi `scripts/spike_array_filter.py` lúc 2026-10-12T00:12:57. pg_search 0.25.9, probe 0.02, LIMIT 50, 20 truy vấn × 3 lần, seed 42.

## Độ chọn lọc của bộ lọc

| Bộ lọc | Số dòng còn lại | Tỉ lệ |
|---|---:|---:|
| peanut | 31,764 / 32,719 | 97.1% |
| milk | 12,611 / 32,719 | 38.5% |
| milk_egg_wheat | 7,131 / 32,719 | 21.8% |
| garlic | 21,881 / 32,719 | 66.9% |
| peanut_milk_cilantro | 11,226 / 32,719 | 34.3% |

## Kết quả theo biến thể

| Retriever | Biến thể | Bộ lọc | Pushdown | Lọc native | heap_filter | TopK | Truy vấn hụt | Vi phạm | Overlap với exact | p50 ms |
|---|---|---|---|---|---|---|---:|---:|---:|---:|
| bm25 | (không lọc) | – | | | | | | | 1.0 | 6.2 |
| bm25 | A1_overlap | peanut | có | không | có | có | 0 | 0 | 1.0 | 43.6 |
| bm25 | A2_term_set | peanut | có | có | không | có | 0 | 0 | 1.0 | 6.8 |
| bm25 | B_bool | peanut | có | có | không | có | 0 | 0 | 1.0 | 34.4 |
| bm25 | D_combined | peanut | có | có | không | có | 0 | 0 | 1.0 | 6.6 |
| bm25 | A1_overlap | milk | có | không | có | có | 0 | 0 | 1.0 | 27.0 |
| bm25 | A2_term_set | milk | có | có | không | có | 0 | 0 | 1.0 | 6.6 |
| bm25 | B_bool | milk | có | có | không | có | 0 | 0 | 1.0 | 24.3 |
| bm25 | D_combined | milk | có | có | không | có | 0 | 0 | 1.0 | 6.0 |
| bm25 | A1_overlap | milk_egg_wheat | có | không | có | có | 0 | 0 | 1.0 | 27.8 |
| bm25 | A2_term_set | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 6.9 |
| bm25 | B_bool | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 25.2 |
| bm25 | D_combined | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 6.0 |
| bm25 | A1_overlap | garlic | có | không | có | có | 0 | 0 | 1.0 | 27.9 |
| bm25 | A2_term_set | garlic | có | có | không | có | 0 | 0 | 1.0 | 6.4 |
| bm25 | B_bool | garlic | có | có | không | có | 0 | 0 | 1.0 | 6.6 |
| bm25 | D_combined | garlic | có | có | không | có | 0 | 0 | 1.0 | 6.0 |
| bm25 | A1_overlap | peanut_milk_cilantro | có | không | có | có | 0 | 0 | 1.0 | 28.6 |
| bm25 | A2_term_set | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 6.5 |
| bm25 | B_bool | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 25.1 |
| bm25 | D_combined | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 8.5 |
| dense | (không lọc) | – | | | | | | | 0.446 | 55.6 |
| dense | A1_overlap | peanut | có | không | có | có | 0 | 0 | 0.456 | 76.4 |
| dense | A2_term_set | peanut | có | có | không | có | 0 | 0 | 0.456 | 61.4 |
| dense | B_bool | peanut | có | có | không | có | 0 | 0 | 0.456 | 72.2 |
| dense | D_combined | peanut | có | có | không | có | 0 | 0 | 1.0 | 47.9 |
| dense | A1_overlap | milk | có | không | có | có | 0 | 0 | 0.588 | 75.9 |
| dense | A2_term_set | milk | có | có | không | có | 0 | 0 | 0.588 | 64.3 |
| dense | B_bool | milk | có | có | không | có | 0 | 0 | 0.588 | 71.9 |
| dense | D_combined | milk | có | có | không | có | 0 | 0 | 1.0 | 48.1 |
| dense | A1_overlap | milk_egg_wheat | có | không | có | có | 0 | 0 | 0.682 | 75.6 |
| dense | A2_term_set | milk_egg_wheat | có | có | không | có | 0 | 0 | 0.682 | 67.3 |
| dense | B_bool | milk_egg_wheat | có | có | không | có | 0 | 0 | 0.682 | 71.5 |
| dense | D_combined | milk_egg_wheat | có | có | không | có | 0 | 0 | 1.0 | 47.5 |
| dense | A1_overlap | garlic | có | không | có | có | 0 | 0 | 0.462 | 75.3 |
| dense | A2_term_set | garlic | có | có | không | có | 0 | 0 | 0.462 | 62.1 |
| dense | B_bool | garlic | có | có | không | có | 0 | 0 | 0.462 | 58.5 |
| dense | D_combined | garlic | có | có | không | có | 0 | 0 | 1.0 | 48.4 |
| dense | A1_overlap | peanut_milk_cilantro | có | không | có | có | 0 | 0 | 0.605 | 76.7 |
| dense | A2_term_set | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 0.605 | 69.9 |
| dense | B_bool | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 0.605 | 74.9 |
| dense | D_combined | peanut_milk_cilantro | có | có | không | có | 0 | 0 | 1.0 | 48.5 |

## Đánh giá theo luật quyết định (tiêu chí 1–4)

| Biến thể | Đạt | Lọc native trong index | Overlap dense thấp nhất | Lỗi |
|---|---|---|---:|---:|
| A1_overlap | có | không | 0.456 | 0 |
| A2_term_set | có | có | 0.456 | 0 |
| B_bool | có | có | 0.456 | 0 |
