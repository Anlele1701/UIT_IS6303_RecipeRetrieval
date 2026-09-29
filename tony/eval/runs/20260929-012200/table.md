298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 50.0 | 136.1 |
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 740.1 | 1154.7 |
| dense | fixed | 0.614 | 0.708 | 0.795 | 0.470 | 0.491 | 0.522 | 68.5 | 158.4 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 50.1 | 114.6 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 753.9 | 1073.0 |
| dense | semantic | 0.634 | 0.721 | 0.799 | 0.488 | 0.511 | 0.540 | 65.7 | 144.2 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 50.2 | 132.7 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 738.7 | 1006.6 |
| dense | sentence | 0.607 | 0.698 | 0.789 | 0.475 | 0.494 | 0.524 | 67.2 | 152.5 |
| dense (arm) | fixed | 0.634 | 0.732 | 0.809 | 0.482 | 0.506 | 0.538 | 40.8 | 176.1 |
| fusion (arm) | fixed | 0.671 | 0.758 | 0.856 | 0.529 | 0.551 | 0.579 | 41.1 | 169.2 |
| hybrid (arm) | fixed | 0.735 | 0.815 | 0.876 | 0.549 | 0.584 | 0.610 | 831.1 | 1171.4 |
| dense (arm) | semantic | 0.654 | 0.745 | 0.815 | 0.498 | 0.525 | 0.554 | 40.8 | 155.9 |
| fusion (arm) | semantic | 0.671 | 0.762 | 0.852 | 0.539 | 0.558 | 0.588 | 41.8 | 157.8 |
| hybrid (arm) | semantic | 0.748 | 0.822 | 0.866 | 0.558 | 0.595 | 0.620 | 835.7 | 1128.5 |
| dense (arm) | sentence | 0.641 | 0.728 | 0.815 | 0.489 | 0.514 | 0.543 | 40.2 | 171.6 |
| fusion (arm) | sentence | 0.664 | 0.762 | 0.852 | 0.522 | 0.542 | 0.575 | 41.6 | 169.1 |
| hybrid (arm) | sentence | 0.728 | 0.826 | 0.869 | 0.551 | 0.583 | 0.615 | 842.5 | 1184.6 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, fusion/semantic 2, hybrid/semantic 2, fusion/sentence 6, hybrid/sentence 6, fusion/fixed 3, hybrid/fixed 3, fusion/semantic 4, hybrid/semantic 4, fusion/sentence 7, hybrid/sentence 7.
