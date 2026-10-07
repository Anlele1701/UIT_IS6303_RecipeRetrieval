298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 46.1 | 116.5 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 673.1 | 1059.2 |
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 52.4 | 125.9 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 45.1 | 110.2 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 674.1 | 997.7 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 52.2 | 121.6 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 46.1 | 114.1 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 665.3 | 937.9 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 54.0 | 123.2 |
| dense (arm) | fixed | 0.862 | 0.909 | 0.936 | 0.696 | 0.731 | 0.747 | 32.5 | 108.5 |
| fusion (arm) | fixed | 0.886 | 0.933 | 0.963 | 0.731 | 0.763 | 0.779 | 35.9 | 130.5 |
| hybrid (arm) | fixed | 0.909 | 0.963 | 0.977 | 0.765 | 0.795 | 0.813 | 712.1 | 1073.7 |
| dense (arm) | semantic | 0.872 | 0.916 | 0.950 | 0.704 | 0.741 | 0.755 | 32.4 | 156.7 |
| fusion (arm) | semantic | 0.893 | 0.933 | 0.956 | 0.737 | 0.771 | 0.783 | 35.3 | 148.3 |
| hybrid (arm) | semantic | 0.916 | 0.963 | 0.977 | 0.760 | 0.794 | 0.809 | 741.8 | 1076.5 |
| dense (arm) | sentence | 0.869 | 0.906 | 0.936 | 0.701 | 0.738 | 0.750 | 32.5 | 164.4 |
| fusion (arm) | sentence | 0.879 | 0.926 | 0.956 | 0.717 | 0.751 | 0.767 | 35.7 | 153.6 |
| hybrid (arm) | sentence | 0.913 | 0.970 | 0.980 | 0.761 | 0.792 | 0.811 | 728.6 | 1099.5 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, dense/fixed 8, fusion/semantic 2, hybrid/semantic 2, dense/semantic 7, fusion/sentence 6, hybrid/sentence 6, dense/sentence 12, dense/fixed 21, fusion/fixed 3, hybrid/fixed 3, dense/semantic 16, fusion/semantic 4, hybrid/semantic 4, dense/sentence 23, fusion/sentence 7, hybrid/sentence 7.
