298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 34.8 | 51.9 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 670.1 | 953.8 |
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 43.1 | 55.6 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 34.0 | 43.5 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 667.8 | 926.4 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 43.1 | 54.5 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 34.2 | 42.9 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 654.3 | 924.2 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 43.2 | 55.9 |
| dense (arm) | fixed | 0.862 | 0.909 | 0.940 | 0.696 | 0.731 | 0.747 | 83.4 | 138.7 |
| fusion (arm) | fixed | 0.889 | 0.933 | 0.963 | 0.730 | 0.764 | 0.778 | 72.2 | 101.0 |
| hybrid (arm) | fixed | 0.913 | 0.963 | 0.977 | 0.765 | 0.796 | 0.813 | 764.6 | 1075.5 |
| dense (arm) | semantic | 0.872 | 0.919 | 0.953 | 0.703 | 0.739 | 0.754 | 83.7 | 156.9 |
| fusion (arm) | semantic | 0.889 | 0.933 | 0.956 | 0.738 | 0.770 | 0.784 | 71.6 | 89.7 |
| hybrid (arm) | semantic | 0.916 | 0.963 | 0.977 | 0.760 | 0.794 | 0.809 | 782.1 | 1094.8 |
| dense (arm) | sentence | 0.872 | 0.913 | 0.936 | 0.702 | 0.739 | 0.753 | 85.3 | 143.5 |
| fusion (arm) | sentence | 0.879 | 0.926 | 0.956 | 0.718 | 0.752 | 0.768 | 73.7 | 96.9 |
| hybrid (arm) | sentence | 0.913 | 0.970 | 0.980 | 0.761 | 0.792 | 0.811 | 766.6 | 1108.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, dense/fixed 8, fusion/semantic 2, hybrid/semantic 2, dense/semantic 7, fusion/sentence 6, hybrid/sentence 6, dense/sentence 12, dense/fixed 21, fusion/fixed 4, hybrid/fixed 4, dense/semantic 16, fusion/semantic 4, hybrid/semantic 4, dense/sentence 22, fusion/sentence 7, hybrid/sentence 7.
