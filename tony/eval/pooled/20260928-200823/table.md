298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 765.9 | 1245.8 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 735.1 | 1096.7 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 735.6 | 1091.5 |
| hybrid (arm) | fixed | 0.970 | 0.977 | 0.980 | 0.894 | 0.913 | 0.915 | 919.5 | 1561.1 |
| hybrid (arm) | semantic | 0.966 | 0.977 | 0.977 | 0.895 | 0.912 | 0.916 | 920.6 | 1610.8 |
| hybrid (arm) | sentence | 0.966 | 0.977 | 0.980 | 0.888 | 0.907 | 0.910 | 898.3 | 1450.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6.
