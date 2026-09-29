298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | fixed | 0.852 | 0.903 | 0.930 | 0.691 | 0.725 | 0.742 | 67.8 | 134.4 |
| fusion | fixed | 0.876 | 0.923 | 0.963 | 0.714 | 0.748 | 0.763 | 48.6 | 120.9 |
| hybrid | fixed | 0.916 | 0.966 | 0.977 | 0.767 | 0.799 | 0.816 | 970.7 | 1613.9 |
| sparse | fixed | 0.836 | 0.909 | 0.933 | 0.689 | 0.717 | 0.741 | 15.6 | 23.6 |
| dense | semantic | 0.859 | 0.896 | 0.943 | 0.697 | 0.732 | 0.744 | 64.9 | 121.9 |
| fusion | semantic | 0.879 | 0.940 | 0.960 | 0.725 | 0.756 | 0.776 | 47.4 | 90.5 |
| hybrid | semantic | 0.919 | 0.963 | 0.977 | 0.758 | 0.793 | 0.808 | 1018.7 | 1544.7 |
| sparse | semantic | 0.822 | 0.896 | 0.936 | 0.664 | 0.694 | 0.718 | 16.7 | 24.2 |
| dense | sentence | 0.842 | 0.883 | 0.926 | 0.691 | 0.723 | 0.736 | 64.8 | 112.0 |
| fusion | sentence | 0.852 | 0.913 | 0.953 | 0.703 | 0.732 | 0.752 | 47.6 | 86.6 |
| hybrid | sentence | 0.913 | 0.963 | 0.977 | 0.761 | 0.793 | 0.810 | 1010.7 | 1443.8 |
| sparse | sentence | 0.822 | 0.889 | 0.936 | 0.668 | 0.697 | 0.719 | 16.5 | 24.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, fusion/semantic 2, hybrid/semantic 2, fusion/sentence 6, hybrid/sentence 6.
