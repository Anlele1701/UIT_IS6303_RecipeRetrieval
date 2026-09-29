298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 39.3 | 49.8 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 38.4 | 48.5 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 40.1 | 50.6 |
| fusion (arm) | fixed | 0.648 | 0.755 | 0.859 | 0.507 | 0.526 | 0.560 | 39.1 | 49.6 |
| fusion (arm) | semantic | 0.661 | 0.779 | 0.852 | 0.522 | 0.541 | 0.579 | 38.3 | 48.9 |
| fusion (arm) | sentence | 0.648 | 0.755 | 0.846 | 0.505 | 0.525 | 0.559 | 40.4 | 50.4 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, fusion/semantic 2, fusion/sentence 6, fusion/fixed 2, fusion/semantic 2, fusion/sentence 6.
