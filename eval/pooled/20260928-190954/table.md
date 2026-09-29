298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 49.2 | 111.0 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 1197.7 | 2021.9 |
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 63.6 | 147.9 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 46.9 | 97.0 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 1209.6 | 1852.9 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 59.6 | 139.3 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 49.1 | 113.9 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 1173.5 | 1836.7 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 62.9 | 171.8 |
| dense (arm) | fixed | 0.862 | 0.909 | 0.940 | 0.696 | 0.731 | 0.747 | 111.6 | 474.6 |
| fusion (arm) | fixed | 0.889 | 0.933 | 0.963 | 0.730 | 0.764 | 0.778 | 100.4 | 399.1 |
| hybrid (arm) | fixed | 0.913 | 0.963 | 0.977 | 0.765 | 0.796 | 0.813 | 1427.6 | 2123.8 |
| dense (arm) | semantic | 0.872 | 0.919 | 0.953 | 0.703 | 0.739 | 0.754 | 110.2 | 507.5 |
| fusion (arm) | semantic | 0.889 | 0.933 | 0.956 | 0.738 | 0.770 | 0.784 | 97.1 | 318.0 |
| hybrid (arm) | semantic | 0.916 | 0.963 | 0.977 | 0.760 | 0.794 | 0.809 | 1435.9 | 2132.4 |
| dense (arm) | sentence | 0.872 | 0.913 | 0.936 | 0.702 | 0.739 | 0.753 | 126.9 | 669.4 |
| fusion (arm) | sentence | 0.879 | 0.926 | 0.956 | 0.718 | 0.752 | 0.768 | 112.0 | 480.6 |
| hybrid (arm) | sentence | 0.913 | 0.970 | 0.980 | 0.761 | 0.792 | 0.811 | 1414.9 | 2164.9 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, fusion/semantic 2, hybrid/semantic 2, fusion/sentence 6, hybrid/sentence 6, fusion/fixed 4, hybrid/fixed 4, fusion/semantic 4, hybrid/semantic 4, fusion/sentence 7, hybrid/sentence 7.
