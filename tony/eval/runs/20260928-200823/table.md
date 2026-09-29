298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 765.9 | 1245.8 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 735.1 | 1096.7 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 735.6 | 1091.5 |
| hybrid (arm) | fixed | 0.799 | 0.862 | 0.879 | 0.668 | 0.694 | 0.715 | 919.5 | 1561.1 |
| hybrid (arm) | semantic | 0.789 | 0.852 | 0.879 | 0.657 | 0.682 | 0.703 | 920.6 | 1610.8 |
| hybrid (arm) | sentence | 0.779 | 0.856 | 0.876 | 0.649 | 0.673 | 0.698 | 898.3 | 1450.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6.
