298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 40.0 | 50.6 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 39.1 | 48.9 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 40.9 | 51.6 |
| fusion (arm) | fixed | 0.906 | 0.933 | 0.963 | 0.730 | 0.769 | 0.778 | 40.0 | 50.2 |
| fusion (arm) | semantic | 0.896 | 0.933 | 0.960 | 0.737 | 0.771 | 0.783 | 38.9 | 49.0 |
| fusion (arm) | sentence | 0.889 | 0.936 | 0.953 | 0.719 | 0.756 | 0.772 | 40.9 | 51.0 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, fusion/semantic 2, fusion/sentence 6, fusion/fixed 2, fusion/semantic 2, fusion/sentence 6.
