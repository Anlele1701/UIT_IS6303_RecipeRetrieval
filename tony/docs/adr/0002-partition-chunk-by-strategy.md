---
status: accepted
---

# Partition the chunk table by Chunking strategy

Chunking strategies are compared in an ablation study, so one strategy's rows must not change another's scores. ParadeDB computes BM25 statistics (document count, document frequency, average length) over the whole index, and a `strategy` filter doesn't narrow them. Adding another strategy's rows changed an existing score from 2.2991 to 1.2910. A table can have only one ParadeDB index, so partial indexes per strategy aren't possible. We make `chunk` a table partitioned `BY LIST (strategy)`, with one partition and one ParadeDB index per strategy. Queries keep targeting `chunk` with `WHERE strategy = %s`, and the planner prunes to that partition's index, including when the name is a bound parameter.

## Considered Options

- **One table, one index, `strategy` column (the current setup):** simplest, but scores leak across strategies.
- **One unpartitioned table per strategy:** isolated, but every query has to build its table name, which can't be a bound parameter and needs an allowlist in each place it's used.
- **One database per strategy:** full isolation, but three connection pools and routing for what partitions give inside one Postgres.

## Consequences

- The primary key becomes `(id, strategy)`, since a partitioned table's key must include the partition column.
- There is no DEFAULT partition. Inserting chunks for a strategy without a partition fails, so a new strategy is always added deliberately.
- A query on `chunk` without a `strategy` condition scans every partition and mixes strategies. The API always requires a strategy.
- Raw `pdb.score` values aren't comparable across strategies. Only rankings are.
