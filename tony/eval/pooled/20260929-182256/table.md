298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 56.1 | 82.6 |
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 54.1 | 91.7 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 1461.6 | 2536.2 |
| sparse | fixed | 0.836 | 0.909 | 0.933 | 0.689 | 0.717 | 0.741 | 13.0 | 19.0 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 57.8 | 81.1 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 53.5 | 80.6 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 1505.4 | 2407.4 |
| sparse | semantic | 0.822 | 0.896 | 0.936 | 0.664 | 0.694 | 0.718 | 14.8 | 22.1 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 58.4 | 82.3 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 53.7 | 80.0 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 1449.4 | 2293.2 |
| sparse | sentence | 0.822 | 0.889 | 0.936 | 0.668 | 0.697 | 0.719 | 14.9 | 23.2 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): dense/fixed 8, fusion/fixed 2, hybrid/fixed 2, sparse/fixed 3, dense/semantic 7, fusion/semantic 2, hybrid/semantic 2, sparse/semantic 4, dense/sentence 12, fusion/sentence 6, hybrid/sentence 6, sparse/sentence 2.
