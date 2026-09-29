298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 976.8 | 1598.6 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 976.8 | 1573.2 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 967.3 | 1581.4 |
| hybrid (arm) | fixed | 0.943 | 0.970 | 0.977 | 0.850 | 0.870 | 0.879 | 2906.2 | 4746.0 |
| hybrid (arm) | semantic | 0.943 | 0.966 | 0.973 | 0.838 | 0.861 | 0.869 | 2866.9 | 4915.6 |
| hybrid (arm) | sentence | 0.946 | 0.960 | 0.977 | 0.842 | 0.866 | 0.871 | 2874.9 | 4605.4 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6.
