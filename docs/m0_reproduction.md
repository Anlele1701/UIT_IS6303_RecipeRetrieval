# Tái lập A1 (M0)

Sinh tự động bởi `scripts/compare_a1.py` lúc 2026-10-12T03:20:28. Chiến lược `semantic`, 298 truy vấn, qrels pooled, reranker `mixedbread-ai/mxbai-rerank-base-v1`, pg_search 0.25.9.

## 1. Cấu hình phục vụ (probe 0.02)

Run `eval/runs/20261012-002242` so với A1 eval/pooled/20261006-224100.

| Cấu hình | Metric | A1 | A3 | Δ | Trong ngưỡng |
|---|---|---:|---:|---:|---|
| fusion | recall@5 | 0.879 | 0.886 | +0.007 | có (±0.01) |
| fusion | recall@10 | 0.940 | 0.926 | -0.013 | KHÔNG (±0.01) |
| fusion | mrr | 0.725 | 0.722 | -0.003 | có (±0.01) |
| fusion | ndcg@10 | 0.776 | 0.770 | -0.005 | có (±0.01) |
| hybrid | recall@5 | 0.966 | 0.966 | +0.000 | có (±0.015) |
| hybrid | recall@10 | 0.977 | 0.977 | +0.000 | có (±0.015) |
| hybrid | mrr | 0.895 | 0.893 | -0.003 | có (±0.015) |
| hybrid | ndcg@10 | 0.916 | 0.914 | -0.002 | có (±0.015) |

Kết luận: có metric vượt ngưỡng.

## 2. Dense chính xác (probe 1.0), loại bỏ ảnh hưởng của index ANN

Run `eval/runs/20261012-031749` so với A1 eval/pooled/20260929-195231 (arm exact-dense, probe 1.0).

| Cấu hình | Metric | A1 | A3 | Δ | Trong ngưỡng |
|---|---|---:|---:|---:|---|
| dense | recall@5 | 0.873 | 0.873 | +0.000 | có (±0.0005) |
| dense | recall@10 | 0.919 | 0.919 | +0.000 | có (±0.0005) |
| dense | mrr | 0.703 | 0.703 | +0.000 | có (±0.0005) |
| dense | ndcg@10 | 0.754 | 0.754 | +0.000 | có (±0.0005) |
| fusion | recall@5 | 0.889 | 0.889 | +0.000 | có (±0.0005) |
| fusion | recall@10 | 0.933 | 0.933 | +0.000 | có (±0.0005) |
| fusion | mrr | 0.738 | 0.738 | +0.000 | có (±0.0005) |
| fusion | ndcg@10 | 0.784 | 0.784 | +0.000 | có (±0.0005) |

Kết luận: trùng A1.

## Độ trễ p50 end-to-end (chỉ ghi nhận, khác máy)

- fusion: A1 67.4 ms, A3 2148.7 ms
- hybrid: A1 724.9 ms, A3 33149.7 ms
