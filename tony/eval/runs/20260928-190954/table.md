298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 49.2 | 111.0 |
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 1197.7 | 2021.9 |
| dense | fixed | 0.614 | 0.708 | 0.795 | 0.470 | 0.491 | 0.522 | 63.6 | 147.9 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 46.9 | 97.0 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 1209.6 | 1852.9 |
| dense | semantic | 0.634 | 0.721 | 0.799 | 0.488 | 0.511 | 0.540 | 59.6 | 139.3 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 49.1 | 113.9 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 1173.5 | 1836.7 |
| dense | sentence | 0.607 | 0.698 | 0.789 | 0.475 | 0.494 | 0.524 | 62.9 | 171.8 |
| dense (arm) | fixed | 0.634 | 0.735 | 0.812 | 0.483 | 0.506 | 0.539 | 111.6 | 474.6 |
| fusion (arm) | fixed | 0.668 | 0.758 | 0.856 | 0.532 | 0.551 | 0.581 | 100.4 | 399.1 |
| hybrid (arm) | fixed | 0.735 | 0.815 | 0.876 | 0.549 | 0.584 | 0.610 | 1427.6 | 2123.8 |
| dense (arm) | semantic | 0.654 | 0.745 | 0.819 | 0.497 | 0.523 | 0.553 | 110.2 | 507.5 |
| fusion (arm) | semantic | 0.671 | 0.762 | 0.852 | 0.540 | 0.559 | 0.588 | 97.1 | 318.0 |
| hybrid (arm) | semantic | 0.748 | 0.822 | 0.866 | 0.558 | 0.595 | 0.620 | 1435.9 | 2132.4 |
| dense (arm) | sentence | 0.641 | 0.735 | 0.815 | 0.490 | 0.514 | 0.545 | 126.9 | 669.4 |
| fusion (arm) | sentence | 0.664 | 0.758 | 0.852 | 0.523 | 0.543 | 0.574 | 112.0 | 480.6 |
| hybrid (arm) | sentence | 0.725 | 0.826 | 0.869 | 0.551 | 0.581 | 0.615 | 1414.9 | 2164.9 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, fusion/semantic 2, hybrid/semantic 2, fusion/sentence 6, hybrid/sentence 6, fusion/fixed 4, hybrid/fixed 4, fusion/semantic 4, hybrid/semantic 4, fusion/sentence 7, hybrid/sentence 7.
