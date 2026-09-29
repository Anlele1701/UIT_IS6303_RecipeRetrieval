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
| fusion | fixed | high | 0.929 | 0.974 | 0.994 | 0.800 | 0.827 | 0.841 |
| fusion | fixed | low | 0.819 | 0.868 | 0.931 | 0.622 | 0.663 | 0.679 |
| fusion | semantic | high | 0.929 | 0.981 | 0.994 | 0.822 | 0.842 | 0.859 |
| fusion | semantic | low | 0.826 | 0.896 | 0.924 | 0.621 | 0.664 | 0.687 |
| fusion | sentence | high | 0.922 | 0.961 | 0.987 | 0.791 | 0.818 | 0.832 |
| fusion | sentence | low | 0.778 | 0.861 | 0.917 | 0.609 | 0.640 | 0.667 |
