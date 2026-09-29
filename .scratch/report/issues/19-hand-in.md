# What the hand-in includes besides the page

Type: grilling
Status: resolved
Assignee: Tony Trinh
Blocked by:
Parent: ../map.md

## Question

The brief sets no format rules. Decide what gets handed in with the Report page: nothing else, a PDF export of the page, slides, a live demo of the served API and UI, or the repo link. Anything chosen here may add a page-spec item (a print stylesheet, for example).

## Answer

Decided with the human (2026-09-29).

- Hand-in is a live presentation plus the code on GitHub. Nobody reads the report alone later, so no PDF export, no print stylesheet, no hosting.
- No slides. The Report page is presented directly; the page spec's quality bar has to carry that.
- Live demo on the served search UI, `semantic` strategy, three case-study queries: q155 (Dense wins, stew vs soup), q012 (Sparse wins, exact ingredients), q076 (Fusion baseline misses, Hybrid first). Matches §6.4.
- README gets two sections:
  - "Demo": the three queries and what to point out in each.
  - "Results": links the Report run's `eval/runs/20260928-122309/table.md` (already written by `evaluate.py`) with run id and commit `466b46a`. No hand-copied numbers, no run instructions for the page.
- Nothing added to the page itself. The two README sections are page-spec items.
