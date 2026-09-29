298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 1456.4 | 2058.2 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 1442.9 | 2097.7 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 1444.2 | 2002.0 |
| hybrid (arm) | fixed | 0.721 | 0.822 | 0.886 | 0.546 | 0.576 | 0.609 | 2346.5 | 3120.3 |
| hybrid (arm) | semantic | 0.735 | 0.809 | 0.872 | 0.549 | 0.584 | 0.608 | 2322.5 | 3123.4 |
| hybrid (arm) | sentence | 0.715 | 0.805 | 0.872 | 0.544 | 0.574 | 0.603 | 2281.2 | 2988.7 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 3, hybrid/sentence 3.
