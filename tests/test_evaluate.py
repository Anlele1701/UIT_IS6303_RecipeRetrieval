import csv
import json

import pytest

import evaluate
import ingest
from api import config
from conftest import add_strategy

QUERIES = [
    {"query_id": "q001", "text": "garlic shrimp", "recipe_id": 1, "recipe_title": "Garlic Shrimp"},
    {"query_id": "q002", "text": "steeped tea", "recipe_id": 3, "recipe_title": "Tea"},
]


@pytest.fixture
def loaded_db(recipes, fake_embed):
    """RECIPES chunked under `sentence`; `fixed` registered but not loaded, so never in a default run."""
    ingest.run(recipes, ["chunk", "sentence"])
    add_strategy(recipes, "fixed", loaded=False)
    return recipes


@pytest.fixture
def query_set(tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text("".join(json.dumps(q) + "\n" for q in QUERIES))
    return path


def summary_embedding(conn, recipe_id):
    """A fake embedder's answer: the stored vector of the Recipe's Summary chunk."""
    return conn.execute("SELECT embedding::text FROM chunk WHERE recipe_id = %s AND kind = 'summary'",
                        [recipe_id]).fetchone()[0]


def toast_first(query, texts):
    """A fake reranker scorer: Toast's Chunks beat everything, so Reranking visibly reorders."""
    return [1.0 if t.startswith("Toast") else 0.0 for t in texts]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_an_evaluation_run_writes_its_folder_and_ranks_the_known_item_first(loaded_db, query_set, tmp_path):
    calls, scored = [], []

    def embedder(text):
        calls.append(text)
        return summary_embedding(loaded_db, 1)  # every query "means" Garlic Shrimp to Dense

    def scorer(query, texts):
        scored.append(query)
        return toast_first(query, texts)

    run_dir = evaluate.run(loaded_db, embedder, scorer, query_set=query_set, out=tmp_path / "runs")

    assert {p.name for p in run_dir.iterdir()} == {
        "settings.json", "metrics.json", "metrics.csv", "per_query.csv", "table.md", "recipes.csv", "corpus.json"}
    assert calls == ["garlic shrimp", "garlic shrimp", "steeped tea"]  # warm-up, then one per query
    assert scored == calls  # Hybrid reranks once per query, the warm-up included

    settings = json.loads((run_dir / "settings.json").read_text())
    assert settings["strategies"] == ["sentence"]
    assert settings["configs"] == ["sparse", "dense", "fusion", "hybrid"]
    assert settings["queries"] == 2 and len(settings["query_set_sha256"]) == 64
    assert settings["hybrid_candidates"] == config.HYBRID_CANDIDATES
    assert settings["rerank_top"] == config.RERANK_TOP and settings["rerank_model"] == config.RERANK_MODEL
    assert settings["pg_search_version"] and settings["vector_cluster_max_probe"] == 0.02

    ranks = {(r["config"], r["query_id"]): r["rank"] for r in read_csv(run_dir / "per_query.csv")}
    assert set(ranks) == {(c, q) for c in ("sparse", "dense", "fusion", "hybrid") for q in ("q001", "q002")}
    assert ranks["sparse", "q001"] == ranks["dense", "q001"] == ranks["sparse", "q002"] == "1"
    assert ranks["fusion", "q001"] == "1" and ranks["hybrid", "q001"] == "2"  # Reranking put Toast on top

    rows = {r["config"]: r for r in json.loads((run_dir / "metrics.json").read_text())}
    assert rows["sparse"]["mrr"] == 1.0 and rows["sparse"]["queries"] == 2
    assert set(rows["sparse"]["latency_ms"]) == {"total", "sparse"}
    assert set(rows["dense"]["latency_ms"]) == {"total", "embed", "dense"}
    assert set(rows["fusion"]["latency_ms"]) == {"total", "embed", "sparse", "dense", "rrf"}
    assert set(rows["hybrid"]["latency_ms"]) == {"total", "embed", "sparse", "dense", "rrf", "rerank"}
    assert rows["hybrid"]["short_lists"] == 2  # 3 Recipes in the DB: every list is short of 20
    table = (run_dir / "table.md").read_text()
    assert "| sparse | sentence | 1.000 |" in table and "| hybrid | sentence |" in table


def test_fusion_ranks_the_same_candidates_that_hybrid_reranks(loaded_db, query_set, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RERANK_TOP", 1)  # the served cut before Reranking
    run_dir = evaluate.run(loaded_db, lambda text: summary_embedding(loaded_db, 1), toast_first,
                           configs=["fusion", "hybrid"], query_set=query_set, out=tmp_path)
    tops = {(r["config"], r["query_id"]): r["top_recipe_ids"] for r in read_csv(run_dir / "per_query.csv")}
    assert tops["fusion", "q001"] == tops["hybrid", "q001"] == "1"  # Toast is outside the cut, so can't win


def test_a_run_with_hybrid_needs_a_reranker_scorer(loaded_db, query_set, tmp_path):
    with pytest.raises(ValueError, match="reranker"):
        evaluate.run(loaded_db, lambda text: summary_embedding(loaded_db, 1), configs=["hybrid"],
                     query_set=query_set, out=tmp_path)


def test_a_run_can_pick_configs_strategies_and_a_query_limit(loaded_db, query_set, tmp_path):
    run_dir = evaluate.run(loaded_db, lambda text: pytest.fail("Sparse needs no embedding"),
                           configs=["sparse"], strategy_names=["sentence"], query_set=query_set, limit=1,
                           out=tmp_path)
    rows = read_csv(run_dir / "per_query.csv")
    assert [(r["config"], r["strategy"], r["query_id"]) for r in rows] == [("sparse", "sentence", "q001")]


def test_an_unloaded_strategy_is_refused_by_name(loaded_db, query_set, tmp_path):
    with pytest.raises(ValueError, match="'fixed' is not loaded yet"):
        evaluate.run(loaded_db, lambda text: "", toast_first, strategy_names=["fixed"], query_set=query_set,
                     out=tmp_path)


def test_the_command_defaults_to_every_config_and_loaded_strategy():
    a = evaluate.parse_args([])
    assert a.configs is None and a.strategies is None and a.limit is None
    assert a.queries == evaluate.QUERY_SET
    with pytest.raises(SystemExit):
        evaluate.parse_args(["--configs", "bm25"])


def test_config_order_rotates_so_each_pair_goes_first_once_per_cycle():
    pairs = [("sparse", "default"), ("dense", "default"), ("hybrid", "default")]
    assert evaluate.rotated(pairs, 0) == pairs
    assert evaluate.rotated(pairs, 1) == [("dense", "default"), ("hybrid", "default"), ("sparse", "default")]
    assert [evaluate.rotated(pairs, i)[0] for i in range(3, 6)] == pairs  # the cycle repeats


def test_an_ablation_run_writes_the_arm_beside_its_default(loaded_db, query_set, tmp_path, monkeypatch):
    monkeypatch.setitem(evaluate.ARMS, "rerank-top-1", {"configs": ["hybrid"], "set": {"rerank_top": 1}})
    run_dir = evaluate.run(loaded_db, lambda text: summary_embedding(loaded_db, 1), toast_first,
                           arm="rerank-top-1", query_set=query_set, out=tmp_path)

    ranks = {(r["config"], r["variant"], r["query_id"]): r["rank"] for r in read_csv(run_dir / "per_query.csv")}
    assert set(ranks) == {("hybrid", v, q) for v in ("default", "arm") for q in ("q001", "q002")}
    assert ranks["hybrid", "default", "q001"] == "2"  # Reranking puts Toast on top
    assert ranks["hybrid", "arm", "q001"] == "1"  # the cut to 1 keeps Toast out

    settings = json.loads((run_dir / "settings.json").read_text())
    assert settings["configs"] == ["hybrid"]
    assert settings["arm"] == {"key": "rerank-top-1", "configs": ["hybrid"], "set": {"rerank_top": 1}}
    rows = json.loads((run_dir / "metrics.json").read_text())
    assert {(r["config"], r["variant"]) for r in rows} == {("hybrid", "default"), ("hybrid", "arm")}
    assert {r["variant"] for r in read_csv(run_dir / "metrics.csv")} == {"default", "arm"}


def test_a_reranker_arm_reranks_with_the_arm_scorer(loaded_db, query_set, tmp_path, monkeypatch):
    embed = lambda text: summary_embedding(loaded_db, 1)  # noqa: E731
    with pytest.raises(ValueError, match="arm_scorer"):
        evaluate.run(loaded_db, embed, toast_first, arm="reranker-minilm-l6", query_set=query_set, out=tmp_path)

    run_dir = evaluate.run(loaded_db, embed, toast_first, arm="reranker-minilm-l6",
                           arm_scorer=lambda query, texts: [0.0] * len(texts), query_set=query_set, out=tmp_path)
    ranks = {(r["variant"], r["query_id"]): r["rank"] for r in read_csv(run_dir / "per_query.csv")}
    assert ranks["default", "q001"] == "2"  # toast_first
    assert ranks["arm", "q001"] == "1"  # all ties: the fused order stands


def test_the_exact_dense_arm_runs_its_three_configs_and_restores_the_probe(loaded_db, query_set, tmp_path):
    run_dir = evaluate.run(loaded_db, lambda text: summary_embedding(loaded_db, 1), toast_first,
                           arm="exact-dense", query_set=query_set, out=tmp_path)
    rows = read_csv(run_dir / "per_query.csv")
    assert {(r["config"], r["variant"]) for r in rows} == {
        (c, v) for c in ("dense", "fusion", "hybrid") for v in ("default", "arm")}
    assert loaded_db.execute("SHOW paradedb.vector_cluster_max_probe").fetchone()[0] == "0.02"


def test_the_hnsw_arm_refuses_to_run_without_an_hnsw_index(loaded_db, query_set, tmp_path):
    with pytest.raises(ValueError, match="HNSW index on chunk_sentence"):
        evaluate.run(loaded_db, lambda text: summary_embedding(loaded_db, 1), toast_first,
                     arm="hnsw-dense", query_set=query_set, out=tmp_path)


def test_the_hnsw_arm_searches_the_hnsw_index_and_leaves_the_default_ranks_alone(loaded_db, query_set, tmp_path):
    embed = lambda text: summary_embedding(loaded_db, 1)  # noqa: E731
    normal = evaluate.run(loaded_db, embed, toast_first, configs=["dense", "fusion", "hybrid"],
                          query_set=query_set, out=tmp_path / "normal")
    loaded_db.execute("CREATE INDEX chunk_sentence_embedding_hnsw ON chunk_sentence "
                      "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")
    for knob in ("enable_seqscan", "enable_sort"):  # 3 Recipes: the planner would otherwise skip the index
        loaded_db.execute(f"SET {knob} = off")
    try:
        run_dir = evaluate.run(loaded_db, embed, toast_first, arm="hnsw-dense", query_set=query_set,
                               out=tmp_path / "arm")
    finally:
        loaded_db.execute("RESET ALL")

    ranks = lambda d, v: {(r["config"], r["query_id"]): r["rank"]  # noqa: E731
                          for r in read_csv(d / "per_query.csv") if r["variant"] == v}
    assert ranks(run_dir, "default") == ranks(normal, "default")
    assert ranks(run_dir, "arm") == ranks(normal, "default")  # exact on 3 Recipes, so HNSW agrees
    arm = json.loads((run_dir / "settings.json").read_text())["arm"]
    assert arm["set"] == {"dense_index": "hnsw", "ef_search": 200}
    assert [(ix["partition"], ix["index"]) for ix in arm["hnsw_indexes"]] == [
        ("chunk_sentence", "chunk_sentence_embedding_hnsw")]
    assert arm["hnsw_indexes"][0]["bytes"] > 0


def test_an_ablation_run_takes_its_configs_from_the_arm(loaded_db, query_set, tmp_path):
    with pytest.raises(ValueError, match="configs"):
        evaluate.run(loaded_db, lambda text: "", toast_first, configs=["sparse"], arm="rrf-k-10",
                     query_set=query_set, out=tmp_path)


def test_a_run_records_the_winning_chunk_kind_and_the_titles_it_ranked(loaded_db, query_set, tmp_path):
    run_dir = evaluate.run(loaded_db, lambda text: summary_embedding(loaded_db, 1), toast_first,
                           configs=["sparse", "dense"], query_set=query_set, out=tmp_path)
    rows = {(r["config"], r["query_id"]): r for r in read_csv(run_dir / "per_query.csv")}
    assert {r["variant"] for r in rows.values()} == {"default"}
    assert rows["dense", "q001"]["best_kind"] == "summary"  # the query vector is Garlic Shrimp's Summary

    titles = {(r["recipe_id"], r["url"], r["title"]) for r in read_csv(run_dir / "recipes.csv")}
    assert titles == {("1", "u0", "Garlic Shrimp"), ("2", "u1", "Toast"), ("3", "u2", "Tea")}


def test_recipes_csv_lists_a_known_recipe_no_config_found(loaded_db, tmp_path):
    query_set = tmp_path / "queries.jsonl"
    query_set.write_text(json.dumps({"query_id": "q001", "text": "steeped tea", "recipe_id": 2,
                                     "recipe_title": "Toast"}) + "\n")
    run_dir = evaluate.run(loaded_db, lambda text: "", configs=["sparse"], query_set=query_set, out=tmp_path)
    assert read_csv(run_dir / "per_query.csv")[0]["rank"] == ""  # Sparse finds Tea, not Toast
    assert {r["title"] for r in read_csv(run_dir / "recipes.csv")} == {"Toast", "Tea"}


def test_a_run_describes_the_corpus_it_searched(loaded_db, query_set, tmp_path):
    run_dir = evaluate.run(loaded_db, lambda text: "", configs=["sparse"], query_set=query_set, out=tmp_path)
    corpus = json.loads((run_dir / "corpus.json").read_text())

    assert corpus["recipes"] == 3 and corpus["categories"] == 1
    sentence = corpus["strategies"]["sentence"]
    assert sentence["parameters"] == {"sentences": 3}
    assert sentence["chunks"]["summary"] == sentence["chunks"]["ingredients"] == 3  # one each per Recipe
    # Step text without the title line. Tea's 3 sentences are one Step; Toast's is the shortest.
    assert sentence["step_chars"]["max"] == len("Boil water. Steep 1/2 hour. Pour.")  # ingest spells out ½
    assert sentence["step_chars"]["min"] == len("Toast the bread.")
    assert sum(sentence["step_chars"]["bins"].values()) == sentence["chunks"]["step"]
    assert corpus["query_recipe_categories"] == {"1": "Main", "3": "Main"}
    assert corpus["category_recipes"] == {"Main": 3}


def test_the_command_runs_one_named_arm_and_no_hand_picked_configs():
    assert evaluate.parse_args([]).arm is None
    assert evaluate.parse_args(["--arm", "rrf-k-10"]).arm == "rrf-k-10"
    with pytest.raises(SystemExit):
        evaluate.parse_args(["--arm", "rrf-k-7"])
    with pytest.raises(SystemExit):
        evaluate.parse_args(["--arm", "rrf-k-10", "--configs", "fusion"])


def test_a_run_with_qrels_counts_a_judged_recipe_as_right(loaded_db, tmp_path):
    query_set = tmp_path / "queries.jsonl"
    query_set.write_text(json.dumps({"query_id": "q001", "text": "steeped tea", "recipe_id": 2,
                                     "recipe_title": "Toast"}) + "\n")
    qrels = tmp_path / "qrels.csv"
    qrels.write_text("query_id,recipe_id,relevant,source,note\nq001,2,1,label,\nq001,3,1,judged,\n")
    run_dir = evaluate.run(loaded_db, lambda text: "", configs=["sparse"], query_set=query_set, out=tmp_path,
                           qrels=qrels)
    (row,) = read_csv(run_dir / "per_query.csv")
    assert row["recipe_id"] == "2" and row["rank"] == "1"  # Tea, judged right, is Sparse's first hit
    assert row["best_kind"]  # the kind of Tea's Chunk, the first right Recipe
    settings = json.loads((run_dir / "settings.json").read_text())
    assert settings["qrels_sha256"] and json.loads((run_dir / "metrics.json").read_text())[0]["recall@5"] == 1.0


def test_the_command_scores_with_the_pooled_qrels_unless_told_not_to():
    assert evaluate.parse_args([]).qrels == str(evaluate.QRELS)
    assert evaluate.parse_args(["--qrels", "none"]).qrels == "none"
