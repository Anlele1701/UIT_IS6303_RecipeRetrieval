# Spike lọc mảng pg_search – nguồn `real`

Sinh tự động bởi `scripts/spike_array_filter.py` lúc 2026-10-14T13:21:43. pg_search 0.25.9, probe 0.02, LIMIT 50, 20 truy vấn × 3 lần, seed 42.

## Độ chọn lọc của bộ lọc

| Bộ lọc | Số dòng còn lại | Tỉ lệ |
|---|---:|---:|
| peanut | 161,912 / 166,438 | 97.3% |
| milk | 59,589 / 166,438 | 35.8% |
| milk_egg_wheat | 31,939 / 166,438 | 19.2% |
| garlic | 109,596 / 166,438 | 65.8% |
| peanut_milk_cilantro | 52,960 / 166,438 | 31.8% |

## Kết quả theo biến thể

| Retriever | Biến thể | Bộ lọc | Pushdown | Lọc native | heap_filter | TopK | Đáp án rỗng | Truy vấn hụt | Vi phạm | Overlap với exact | p50 ms |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| bm25 | (không lọc) | – | | | | | | | | 1.0 | 7.6 |
| bm25 | A1_overlap | peanut | có | không | có | có | 0/20 | 0 | 0 | 1.0 | 31.6 |
| bm25 | A2_term_set | peanut | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 9.0 |
| bm25 | B_bool | peanut | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 20.6 |
| bm25 | D_combined | peanut | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.7 |
| bm25 | A1_overlap | milk | có | không | có | có | 0/20 | 0 | 0 | 1.0 | 32.7 |
| bm25 | A2_term_set | milk | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.5 |
| bm25 | B_bool | milk | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 18.8 |
| bm25 | D_combined | milk | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 9.3 |
| bm25 | A1_overlap | milk_egg_wheat | có | không | có | có | 0/20 | 0 | 0 | 1.0 | 32.7 |
| bm25 | A2_term_set | milk_egg_wheat | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.7 |
| bm25 | B_bool | milk_egg_wheat | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 21.5 |
| bm25 | D_combined | milk_egg_wheat | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 9.3 |
| bm25 | A1_overlap | garlic | có | không | có | có | 0/20 | 0 | 0 | 1.0 | 32.6 |
| bm25 | A2_term_set | garlic | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.3 |
| bm25 | B_bool | garlic | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 7.7 |
| bm25 | D_combined | garlic | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.1 |
| bm25 | A1_overlap | peanut_milk_cilantro | có | không | có | có | 0/20 | 0 | 0 | 1.0 | 38.3 |
| bm25 | A2_term_set | peanut_milk_cilantro | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.5 |
| bm25 | B_bool | peanut_milk_cilantro | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 19.5 |
| bm25 | D_combined | peanut_milk_cilantro | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 8.3 |
| dense | (không lọc) | – | | | | | | | | 0.888 | 20.3 |
| dense | A1_overlap | peanut | có | không | có | có | 0/20 | 0 | 0 | 0.894 | 32.8 |
| dense | A2_term_set | peanut | có | có | không | có | 0/20 | 0 | 0 | 0.894 | 21.4 |
| dense | B_bool | peanut | có | có | không | có | 0/20 | 0 | 0 | 0.894 | 21.6 |
| dense | D_combined | peanut | có | có | không | có | 0/20 | 0 | 0 | 0.999 | 22.7 |
| dense | A1_overlap | milk | có | không | có | có | 0/20 | 0 | 0 | 0.968 | 35.0 |
| dense | A2_term_set | milk | có | có | không | có | 0/20 | 0 | 0 | 0.968 | 27.7 |
| dense | B_bool | milk | có | có | không | có | 0/20 | 0 | 0 | 0.968 | 22.1 |
| dense | D_combined | milk | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 13.9 |
| dense | A1_overlap | milk_egg_wheat | có | không | có | có | 0/20 | 0 | 0 | 0.991 | 37.9 |
| dense | A2_term_set | milk_egg_wheat | có | có | không | có | 0/20 | 0 | 0 | 0.991 | 32.7 |
| dense | B_bool | milk_egg_wheat | có | có | không | có | 0/20 | 0 | 0 | 0.991 | 25.2 |
| dense | D_combined | milk_egg_wheat | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 12.2 |
| dense | A1_overlap | garlic | có | không | có | có | 0/20 | 0 | 0 | 0.927 | 34.9 |
| dense | A2_term_set | garlic | có | có | không | có | 0/20 | 0 | 0 | 0.927 | 25.2 |
| dense | B_bool | garlic | có | có | không | có | 0/20 | 0 | 0 | 0.927 | 25.6 |
| dense | D_combined | garlic | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 19.3 |
| dense | A1_overlap | peanut_milk_cilantro | có | không | có | có | 0/20 | 0 | 0 | 0.971 | 43.0 |
| dense | A2_term_set | peanut_milk_cilantro | có | có | không | có | 0/20 | 0 | 0 | 0.971 | 29.1 |
| dense | B_bool | peanut_milk_cilantro | có | có | không | có | 0/20 | 0 | 0 | 0.971 | 23.5 |
| dense | D_combined | peanut_milk_cilantro | có | có | không | có | 0/20 | 0 | 0 | 1.0 | 13.6 |

## Đánh giá theo luật quyết định (tiêu chí 1–4)

| Biến thể | Đạt | Lọc native trong index | Overlap dense thấp nhất | Dòng không đo được | Lỗi |
|---|---|---|---:|---:|---:|
| A1_overlap | có | không | 0.894 | 0 | 0 |
| A2_term_set | có | có | 0.894 | 0 | 0 |
| B_bool | có | có | 0.894 | 0 | 0 |
| D_combined | có | có | 0.999 | 0 | 0 |
