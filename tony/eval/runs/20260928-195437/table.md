298 queries. Ranks over the top 20 unique Recipes.

| Config | Strategy | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | 0.735 | 0.822 | 0.872 | 0.552 | 0.586 | 0.614 | 692.4 | 1022.0 |
| hybrid | semantic | 0.735 | 0.826 | 0.876 | 0.557 | 0.589 | 0.619 | 693.3 | 966.9 |
| hybrid | sentence | 0.721 | 0.812 | 0.862 | 0.547 | 0.578 | 0.608 | 688.7 | 960.3 |
| hybrid (arm) | fixed | 0.738 | 0.822 | 0.866 | 0.592 | 0.618 | 0.645 | 184.3 | 264.4 |
| hybrid (arm) | semantic | 0.748 | 0.819 | 0.872 | 0.587 | 0.617 | 0.641 | 179.1 | 254.8 |
| hybrid (arm) | sentence | 0.742 | 0.802 | 0.859 | 0.594 | 0.622 | 0.642 | 183.0 | 249.1 |

Queries whose list had fewer than 20 unique Recipes (the missing positions count as misses): hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6, hybrid/fixed 2, hybrid/semantic 2, hybrid/sentence 6.
