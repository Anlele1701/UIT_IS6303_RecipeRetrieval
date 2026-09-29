# Failure analysis

Ranks are over the top 20 unique Recipes; `-` means not found.

## Counts per Chunking strategy

| Strategy | Queries |  |
|---|---:|
| fixed | 298 |  |
| semantic | 298 |  |
| sentence | 298 |  |

## Metrics by word overlap

High overlap: every content word of the query is in the Recipe's text (154 queries). Low: the rest (144 queries).

| Config | Strategy | Overlap | R@5 | R@10 | R@20 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hybrid | fixed | high | 0.961 | 0.994 | 1.000 | 0.846 | 0.871 | 0.882 |
| hybrid | fixed | low | 0.868 | 0.938 | 0.951 | 0.683 | 0.721 | 0.744 |
| hybrid | semantic | high | 0.968 | 0.994 | 1.000 | 0.851 | 0.877 | 0.886 |
| hybrid | semantic | low | 0.868 | 0.931 | 0.951 | 0.658 | 0.703 | 0.724 |
| hybrid | sentence | high | 0.961 | 0.994 | 1.000 | 0.843 | 0.869 | 0.880 |
| hybrid | sentence | low | 0.861 | 0.931 | 0.951 | 0.673 | 0.711 | 0.734 |
