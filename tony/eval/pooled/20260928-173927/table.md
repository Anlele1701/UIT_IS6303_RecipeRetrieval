298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 1514.4 | 2208.7 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 1497.9 | 2170.8 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 1472.7 | 2048.6 |
| hybrid (arm) | fixed | 0.923 | 0.953 | 0.956 | 0.778 | 0.811 | 0.821 | 619.0 | 977.5 |
| hybrid (arm) | semantic | 0.926 | 0.943 | 0.956 | 0.758 | 0.798 | 0.804 | 691.5 | 1002.0 |
| hybrid (arm) | sentence | 0.903 | 0.936 | 0.946 | 0.749 | 0.784 | 0.795 | 652.5 | 982.1 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 294, hybrid/semantic 294, hybrid/sentence 295.
