298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 1514.4 | 2208.7 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 1497.9 | 2170.8 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 1472.7 | 2048.6 |
| hybrid (arm) | fixed | 0.762 | 0.809 | 0.812 | 0.571 | 0.614 | 0.629 | 619.0 | 977.5 |
| hybrid (arm) | semantic | 0.735 | 0.812 | 0.832 | 0.551 | 0.588 | 0.613 | 691.5 | 1002.0 |
| hybrid (arm) | sentence | 0.742 | 0.826 | 0.832 | 0.545 | 0.585 | 0.613 | 652.5 | 982.1 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 294, hybrid/semantic 294, hybrid/sentence 295.
