298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 45.9 | 73.0 |
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 46.1 | 75.2 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 1060.1 | 1794.6 |
| sparse | fixed | 0.836 | 0.909 | 0.933 | 0.689 | 0.717 | 0.741 | 12.9 | 19.6 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 47.1 | 67.9 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 45.1 | 60.1 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 1088.7 | 1728.3 |
| sparse | semantic | 0.822 | 0.896 | 0.936 | 0.664 | 0.694 | 0.718 | 14.6 | 20.9 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 47.7 | 67.8 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 45.6 | 63.1 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 1049.2 | 1691.6 |
| sparse | sentence | 0.822 | 0.889 | 0.936 | 0.668 | 0.697 | 0.719 | 14.8 | 21.2 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): dense/fixed 8, fusion/fixed 2, hybrid/fixed 2, sparse/fixed 3, dense/semantic 7, fusion/semantic 2, hybrid/semantic 2, sparse/semantic 4, dense/sentence 12, fusion/sentence 6, hybrid/sentence 6, sparse/sentence 2.
