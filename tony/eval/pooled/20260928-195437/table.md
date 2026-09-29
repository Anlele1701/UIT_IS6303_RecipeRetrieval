298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 692.4 | 1022.0 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 693.3 | 966.9 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 688.7 | 960.3 |
| hybrid (arm) | fixed | 0.913 | 0.963 | 0.970 | 0.791 | 0.817 | 0.833 | 184.3 | 264.4 |
| hybrid (arm) | semantic | 0.923 | 0.960 | 0.977 | 0.799 | 0.825 | 0.837 | 179.1 | 254.8 |
| hybrid (arm) | sentence | 0.926 | 0.960 | 0.977 | 0.796 | 0.824 | 0.835 | 183.0 | 249.1 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6.
