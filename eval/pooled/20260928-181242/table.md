298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 1456.4 | 2058.2 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 1442.9 | 2097.7 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 1444.2 | 2002.0 |
| hybrid (arm) | fixed | 0.909 | 0.970 | 0.983 | 0.760 | 0.790 | 0.810 | 2346.5 | 3120.3 |
| hybrid (arm) | semantic | 0.916 | 0.966 | 0.980 | 0.747 | 0.783 | 0.800 | 2322.5 | 3123.4 |
| hybrid (arm) | sentence | 0.903 | 0.970 | 0.980 | 0.755 | 0.785 | 0.807 | 2281.2 | 2988.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 3, hybrid/sentence 3.
