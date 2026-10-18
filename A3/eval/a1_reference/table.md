298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.970 | 0.977 | 0.980 | 0.894 | 0.913 | 0.915 | 739.6 | 1263.7 |
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 58.7 | 106.4 |
| hybrid | semantic | 0.966 | 0.977 | 0.977 | 0.895 | 0.912 | 0.916 | 724.9 | 1232.8 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 67.4 | 112.0 |
| hybrid | sentence | 0.966 | 0.977 | 0.980 | 0.888 | 0.907 | 0.910 | 718.3 | 1165.8 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 66.4 | 110.6 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, fusion/fixed 2, hybrid/semantic 2, fusion/semantic 2, hybrid/sentence 6, fusion/sentence 6.
