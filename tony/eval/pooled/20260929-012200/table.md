298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 50.0 | 136.1 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 740.1 | 1154.7 |
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 68.5 | 158.4 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 50.1 | 114.6 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 753.9 | 1073.0 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 65.7 | 144.2 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 50.2 | 132.7 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 738.7 | 1006.6 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 67.2 | 152.5 |
| dense (arm) | fixed | 0.862 | 0.909 | 0.936 | 0.696 | 0.731 | 0.747 | 40.8 | 176.1 |
| fusion (arm) | fixed | 0.893 | 0.933 | 0.963 | 0.728 | 0.763 | 0.776 | 41.1 | 169.2 |
| hybrid (arm) | fixed | 0.909 | 0.963 | 0.977 | 0.765 | 0.795 | 0.813 | 831.1 | 1171.4 |
| dense (arm) | semantic | 0.872 | 0.916 | 0.950 | 0.704 | 0.741 | 0.755 | 40.8 | 155.9 |
| fusion (arm) | semantic | 0.893 | 0.933 | 0.956 | 0.737 | 0.771 | 0.784 | 41.8 | 157.8 |
| hybrid (arm) | semantic | 0.916 | 0.963 | 0.977 | 0.760 | 0.794 | 0.809 | 835.7 | 1128.5 |
| dense (arm) | sentence | 0.869 | 0.906 | 0.936 | 0.701 | 0.738 | 0.750 | 40.2 | 171.6 |
| fusion (arm) | sentence | 0.876 | 0.926 | 0.956 | 0.717 | 0.750 | 0.767 | 41.6 | 169.1 |
| hybrid (arm) | sentence | 0.913 | 0.970 | 0.980 | 0.761 | 0.792 | 0.811 | 842.5 | 1184.6 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, fusion/semantic 2, hybrid/semantic 2, fusion/sentence 6, hybrid/sentence 6, fusion/fixed 3, hybrid/fixed 3, fusion/semantic 4, hybrid/semantic 4, fusion/sentence 7, hybrid/sentence 7.
