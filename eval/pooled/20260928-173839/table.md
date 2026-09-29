298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 39.3 | 49.8 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 38.4 | 48.5 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 40.1 | 50.6 |
| fusion (arm) | fixed | 0.876 | 0.923 | 0.963 | 0.713 | 0.747 | 0.762 | 39.1 | 49.6 |
| fusion (arm) | semantic | 0.879 | 0.940 | 0.960 | 0.727 | 0.757 | 0.777 | 38.3 | 48.9 |
| fusion (arm) | sentence | 0.849 | 0.913 | 0.953 | 0.704 | 0.732 | 0.753 | 40.4 | 50.4 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, fusion/semantic 2, fusion/sentence 6, fusion/fixed 2, fusion/semantic 2, fusion/sentence 6.
