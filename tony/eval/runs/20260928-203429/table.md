298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 976.8 | 1598.6 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 976.8 | 1573.2 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 967.3 | 1581.4 |
| hybrid (arm) | fixed | 0.772 | 0.842 | 0.876 | 0.626 | 0.653 | 0.676 | 2906.2 | 4746.0 |
| hybrid (arm) | semantic | 0.785 | 0.856 | 0.876 | 0.626 | 0.658 | 0.681 | 2866.9 | 4915.6 |
| hybrid (arm) | sentence | 0.762 | 0.836 | 0.869 | 0.622 | 0.647 | 0.671 | 2874.9 | 4605.4 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6.
