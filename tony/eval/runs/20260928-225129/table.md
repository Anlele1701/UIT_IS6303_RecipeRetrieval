298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | fixed | 0.614 | 0.708 | 0.795 | 0.470 | 0.491 | 0.522 | 74.3 | 280.3 |
| fusion | fixed | 0.644 | 0.758 | 0.859 | 0.507 | 0.525 | 0.561 | 47.6 | 180.5 |
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 702.4 | 1237.4 |
| sparse | fixed | 0.631 | 0.732 | 0.789 | 0.506 | 0.523 | 0.557 | 18.6 | 32.0 |
| dense | semantic | 0.634 | 0.721 | 0.799 | 0.488 | 0.511 | 0.540 | 69.0 | 253.5 |
| fusion | semantic | 0.668 | 0.779 | 0.852 | 0.522 | 0.544 | 0.579 | 45.9 | 129.7 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 717.8 | 1255.2 |
| sparse | semantic | 0.634 | 0.732 | 0.802 | 0.490 | 0.512 | 0.544 | 19.3 | 32.0 |
| dense | sentence | 0.607 | 0.698 | 0.789 | 0.475 | 0.494 | 0.524 | 74.0 | 269.0 |
| fusion | sentence | 0.644 | 0.755 | 0.846 | 0.505 | 0.524 | 0.559 | 48.3 | 125.9 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 710.8 | 1067.5 |
| sparse | sentence | 0.641 | 0.732 | 0.805 | 0.488 | 0.513 | 0.543 | 19.4 | 42.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): fusion/fixed 2, hybrid/fixed 2, fusion/semantic 2, hybrid/semantic 2, fusion/sentence 6, hybrid/sentence 6.
