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
| hybrid | fixed | high | 0.864 | 0.922 | 0.961 | 0.685 | 0.721 | 0.740 |
| hybrid | fixed | low | 0.597 | 0.715 | 0.778 | 0.410 | 0.442 | 0.480 |
| hybrid | semantic | high | 0.838 | 0.929 | 0.961 | 0.682 | 0.710 | 0.740 |
| hybrid | semantic | low | 0.625 | 0.715 | 0.785 | 0.422 | 0.460 | 0.490 |
| hybrid | sentence | high | 0.838 | 0.922 | 0.948 | 0.672 | 0.704 | 0.732 |
| hybrid | sentence | low | 0.597 | 0.694 | 0.771 | 0.412 | 0.443 | 0.475 |
