298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | fixed | 0.614 | 0.708 | 0.795 | 0.470 | 0.491 | 0.522 | 56.1 | 82.6 |
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 54.1 | 91.7 |
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 1461.6 | 2536.2 |
| sparse | fixed | 0.631 | 0.732 | 0.789 | 0.506 | 0.523 | 0.557 | 13.0 | 19.0 |
| dense | semantic | 0.634 | 0.721 | 0.799 | 0.488 | 0.511 | 0.540 | 57.8 | 81.1 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 53.5 | 80.6 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 1505.4 | 2407.4 |
| sparse | semantic | 0.634 | 0.732 | 0.802 | 0.490 | 0.512 | 0.544 | 14.8 | 22.1 |
| dense | sentence | 0.607 | 0.698 | 0.789 | 0.475 | 0.494 | 0.524 | 58.4 | 82.3 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 53.7 | 80.0 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 1449.4 | 2293.2 |
| sparse | sentence | 0.641 | 0.732 | 0.805 | 0.488 | 0.513 | 0.543 | 14.9 | 23.2 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): dense/fixed 8, fusion/fixed 2, hybrid/fixed 2, sparse/fixed 3, dense/semantic 7, fusion/semantic 2, hybrid/semantic 2, sparse/semantic 4, dense/sentence 12, fusion/sentence 6, hybrid/sentence 6, sparse/sentence 2.
