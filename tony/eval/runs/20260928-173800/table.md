298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 40.0 | 50.6 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 39.1 | 48.9 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 40.9 | 51.6 |
| fusion (arm) | fixed | 0.674 | 0.768 | 0.862 | 0.523 | 0.546 | 0.577 | 40.0 | 50.2 |
| fusion (arm) | semantic | 0.698 | 0.785 | 0.852 | 0.537 | 0.565 | 0.593 | 38.9 | 49.0 |
| fusion (arm) | sentence | 0.685 | 0.782 | 0.849 | 0.522 | 0.549 | 0.581 | 40.9 | 51.0 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, fusion/semantic 2, fusion/sentence 6, fusion/fixed 2, fusion/semantic 2, fusion/sentence 6.
