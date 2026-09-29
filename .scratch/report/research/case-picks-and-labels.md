# Case picks and labels (proposal, awaiting confirmation)

Ticket: [Pick the case studies and label the every-config misses](../issues/16-pick-cases-and-label-misses.md). Report run `20260928-122309`. Shortlists from `pick_cases.py` (run from the repo root), saved in `pick_cases_shortlists.json`.

Titles map by position after URL dedupe (1-based). The script asserts all 298 Query set titles match.

Ranks below read Sparse / Dense / Fusion baseline / Hybrid; `-` is outside the top 20.

## Shortlist sizes

| bucket | rule (on all 3 Chunking strategies) | size |
|---|---|---:|
| dense_win | Dense ≤ 10 < Sparse | 21 |
| sparse_win | Sparse ≤ 10 < Dense | 23 |
| rerank_hurt | Hybrid below the Fusion baseline | 30 |
| rerank_help | Hybrid in the top 5 and above the Fusion baseline | 42 |
| every-config miss | all 4 configs outside the top 20 | 29 |

## Proposed picks (§6.4, shown on semantic)

| bucket | query | known Recipe | fixed | semantic | sentence | why this one |
|---|---|---|---|---|---|---|
| dense_win | q155 "creamy black bean and tomato stew" | Black Bean and Tomato Soup | -/1/3/1 | -/2/5/2 | -/1/9/2 | "stew" vs "soup": Sparse needs the word, Dense knows they're the same kind of dish |
| sparse_win | q012 "yellow split pea soup with curry powder" | Vegan Split Pea Soup II | 1/-/4/2 | 1/-/4/2 | 1/19/4/2 | exact ingredients; Dense blurs it into every other split pea soup. High overlap (1.0), ties to §6.2 |
| rerank_hurt | q048 "spicy lemon harissa baked wings" | Baked Lemon-Pepper-Harissa Wings | 1/1/1/2 | 1/1/1/2 | 1/1/1/2 | the typical hurt: a 1-rank swap with "Harissa and Lemon-Pepper Wings", a near-duplicate. Matches the §6 claim |
| rerank_help | q076 "greek yogurt with fruit and nuts frozen dessert" | Yogurt Bark | -/-/-/1 | -/17/-/1 | -/14/-/1 | Fusion baseline misses it on all 3, Hybrid puts it first on all 3. The strongest help in the run |
| every-config miss | q066 "moist white cake with sour cream" | Wedding Cake | -/-/-/- | -/-/-/- | -/-/-/- | full word overlap (1.0) and still missed: opaque title, and many sour cream cakes compete |

Runners-up: dense_win q218 (Sparse misses, Dense 1 on all 3, but the "why" is harder to explain); sparse_win q051 Frikadellen; rerank_hurt q229 (Fusion 4–7 → Hybrid 15–20, the worst drop, but not typical); every-config miss q117 "cola" → Long Island Iced Tea (lexical trap).

## Every-config misses (§6.5), 29

| group | count | queries |
|---|---:|---|
| near-duplicate Recipes | 17 | q009, q050, q054, q060, q092, q114, q131, q147, q185, q191, q210, q214, q221, q255, q283, q292, q300 |
| opaque title | 8 | q052 Death By Garlic, q066 Wedding Cake, q098 Macarons, q136 Salata, q182 Sopes, q245 Pasties, q289 Tilapia de Jonghe, q291 Malasadas Dois |
| lexical trap | 3 | q033 ("broccoli cheese" → Broccoli Squares), q117 ("cola" → Coca-Cola Cake), q190 ("potatoes" → potato soups) |
| other | 1 | q163 (right ingredient, wrong course: crawfish bisque/stew for an appetizer dip) |

Check of the provisional §6.5 claim ("most misses come from the one-correct-Recipe ground truth"): holds, narrowly. 17 of 29 have top hits that a person would accept. Suggested wording: "17 of the 29 are near-duplicates: the top hits are arguably right, but the Query set counts only one Recipe as correct." The 8 opaque titles are a separate story (the name hides the dish), not a ground-truth artifact.

## Query set rewrites (§2.3), 57

| reason | proposed | old total |
|---|---:|---:|
| wrong facts | 25 | 23 |
| broken | 7 | 10 |
| too vague | 12 | 10 |
| copies title | 6 | 6 |
| odd wording | 7 | 8 |

- wrong facts: q006, q037, q043, q049, q053, q056, q066, q072, q118, q122, q135, q147, q159, q183, q188, q211, q217, q218, q222, q223, q224, q242, q243, q265, q275
- broken: q032, q138, q148, q150, q228, q235, q261
- too vague: q026, q153, q167, q198, q199, q205, q234, q253, q255, q274, q277, q295
- copies title: q012, q071, q078, q089, q090, q178
- odd wording: q016, q065, q080, q128, q174, q266, q285

Notes:

- The old totals came from the Query set review ("Generate the Query set", evaluation map) and were never stored per query, so they can't be matched one to one. The report should print the confirmed per-query counts, not the old ones.
- The 6 "swapped twice" can't be recovered: `edited_from` keeps only qwen's text, and `queries.jsonl` has one commit. Report it as a count from the review notes, or drop it.
- Overlap mean: the Query set ticket says 0.85 after the accent fix; "Dataset section stats" says 0.80 → 0.84. The bundle computes it, so the page will be right; the ticket text is stale.
