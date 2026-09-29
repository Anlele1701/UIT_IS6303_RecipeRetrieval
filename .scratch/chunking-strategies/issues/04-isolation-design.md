# How the schema keeps strategies isolated

Type: grilling
Status: resolved
Blocked by: 01
Parent: ../map.md

## Question

Given the research findings, which layout keeps each strategy's BM25 and vector scores independent of the other strategies: one table + one index with a filter, one partial index per strategy, a partitioned `chunk` table, or something else? Record as an ADR if it's a real trade-off.

## Answer

Partition `chunk` by list on `strategy`: one partition per Chunking strategy, each with its own ParadeDB index, no default partition. This was chosen over separate tables because it gives the same isolation while keeping one query path (`WHERE strategy = %s`, pruned by the planner), with no table-name routing or allowlist. PK becomes `(id, strategy)`. Recorded as [ADR-0002](../../../docs/adr/0002-partition-chunk-by-strategy.md).

