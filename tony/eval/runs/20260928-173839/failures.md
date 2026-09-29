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
| fusion | fixed | high | 0.779 | 0.896 | 0.955 | 0.638 | 0.658 | 0.696 |
| fusion | fixed | low | 0.500 | 0.611 | 0.757 | 0.368 | 0.382 | 0.418 |
| fusion | semantic | high | 0.812 | 0.903 | 0.961 | 0.670 | 0.693 | 0.722 |
| fusion | semantic | low | 0.514 | 0.646 | 0.736 | 0.364 | 0.384 | 0.426 |
| fusion | sentence | high | 0.805 | 0.864 | 0.942 | 0.635 | 0.667 | 0.686 |
| fusion | sentence | low | 0.472 | 0.639 | 0.743 | 0.366 | 0.371 | 0.424 |
