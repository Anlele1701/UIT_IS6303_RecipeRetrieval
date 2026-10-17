"""scripts/tag.py and `ingest.py retag` on the throwaway test DB (fixtures in conftest.py)."""

import ingest
import tag


def tag_test_db(conn):
    report, tables = tag.tag_all(conn)
    tag.write_tables(conn, tables)
    return report


def test_tag_writes_one_row_per_recipe_with_its_allergens(recipes):
    report = tag_test_db(recipes)
    rows = dict(recipes.execute("SELECT recipe_id, allergens FROM recipe_tag ORDER BY recipe_id").fetchall())
    assert rows == {1: ["crustacean_shellfish"], 2: ["wheat"], 3: []}  # shrimp; bread; tea
    assert report["D4"]["lines"] == 4
    assert recipes.execute("SELECT count(*) FROM recipe_ingredient_norm").fetchone()[0] == 4


def test_tag_marks_a_line_it_cannot_map_as_unknown(recipes):
    tag_test_db(recipes)
    has_unknown, unknown = recipes.execute(
        "SELECT has_unknown, unknown_lines FROM recipe_tag WHERE recipe_id = 3").fetchone()
    assert (has_unknown, unknown) == (True, 1)  # "1 tea bag": no canonical for tea bag


def test_tag_rerun_replaces_instead_of_adding(recipes):
    tag_test_db(recipes)
    tag_test_db(recipes)
    assert recipes.execute("SELECT count(*) FROM recipe_tag").fetchone()[0] == 3


def build(recipes, name="sentence"):
    ingest.run(recipes, ["chunk", name])


def test_retag_copies_tags_keeps_chunk_ids_and_leaves_a_legacy_partition(recipes, fake_embed):
    build(recipes)
    before = recipes.execute("SELECT id, recipe_id, content, embedding::text FROM chunk ORDER BY id").fetchall()
    tag_test_db(recipes)
    ingest.run(recipes, ["retag", "sentence"])
    after = recipes.execute("SELECT id, recipe_id, content, embedding::text FROM chunk ORDER BY id").fetchall()
    assert after == before  # same Chunks, same ids, same embeddings
    tags = dict(recipes.execute("SELECT DISTINCT recipe_id, allergens FROM chunk").fetchall())
    assert tags == {1: ["crustacean_shellfish"], 2: ["wheat"], 3: []}
    assert recipes.execute("SELECT to_regclass('chunk_sentence_legacy') IS NOT NULL").fetchone()[0]
    recipes.execute("DROP TABLE chunk_sentence_legacy")


def test_term_set_filter_excludes_tagged_recipes_inside_the_index(recipes, fake_embed):
    """ADR-0005's filter, on the partition: pg_search 0.25.9 cannot run field term queries via the parent."""
    build(recipes)
    tag_test_db(recipes)
    ingest.run(recipes, ["retag", "sentence"])
    rows = recipes.execute(
        """SELECT DISTINCT recipe_id FROM chunk_sentence WHERE id @@@ pdb.all()
           AND NOT (allergens @@@ pdb.term_set(ARRAY['crustacean_shellfish']))""").fetchall()
    assert sorted(r[0] for r in rows) == [2, 3]
    recipes.execute("DROP TABLE chunk_sentence_legacy")


def test_on_the_parent_only_the_heap_filter_form_works(recipes, fake_embed):
    """Documents a pg_search 0.25.9 limit (see ADR-0005 addendum); fails loudly if an upgrade lifts it."""
    import psycopg
    import pytest
    build(recipes)
    tag_test_db(recipes)
    ingest.run(recipes, ["retag", "sentence"])
    rows = recipes.execute(
        """SELECT DISTINCT recipe_id FROM chunk WHERE id @@@ pdb.all() AND strategy = 'sentence'
           AND NOT (allergens && ARRAY['crustacean_shellfish'])""").fetchall()
    assert sorted(r[0] for r in rows) == [2, 3]
    with pytest.raises(psycopg.errors.UndefinedFile):
        recipes.execute("""SELECT count(*) FROM chunk WHERE id @@@ pdb.all() AND strategy = 'sentence'
                           AND NOT (allergens @@@ pdb.term_set(ARRAY['wheat']))""")
    recipes.execute("DROP TABLE chunk_sentence_legacy")


def test_retag_refuses_when_a_recipe_has_no_tags(recipes, fake_embed):
    build(recipes)
    import pytest
    with pytest.raises(SystemExit, match="no recipe_tag row"):
        ingest.run(recipes, ["retag", "sentence"])


def test_a_new_build_copies_the_tags_from_recipe_tag(recipes, fake_embed):
    tag_test_db(recipes)
    build(recipes)
    tags = dict(recipes.execute("SELECT DISTINCT recipe_id, allergens FROM chunk").fetchall())
    assert tags == {1: ["crustacean_shellfish"], 2: ["wheat"], 3: []}


def test_a_second_retag_keeps_the_older_legacy_under_a_timestamped_name(recipes, fake_embed):
    build(recipes)
    tag_test_db(recipes)
    ingest.run(recipes, ["retag", "sentence"])
    ingest.run(recipes, ["retag", "sentence"])
    kept = [r[0] for r in recipes.execute(
        "SELECT relname FROM pg_class WHERE relname LIKE 'chunk_sentence_legacy%' AND relkind = 'r' ORDER BY relname")]
    assert kept[0] == "chunk_sentence_legacy" and len(kept) == 2 and kept[1].startswith("chunk_sentence_legacy_")
    assert recipes.execute("SELECT count(*) FROM chunk WHERE strategy = 'sentence'").fetchone()[0] > 0
    for t in kept:
        recipes.execute(f'DROP TABLE "{t}"')


def _set_nutrition(conn):
    conn.execute("""UPDATE recipe_nutrition SET calories = 400, saturated_fat_g = 4, sugars_g = 20,
                    dietary_fiber_g = 6, potassium_mg = 300 WHERE recipe_id = 1""")
    conn.execute("UPDATE recipe_nutrition SET calories = 0 WHERE recipe_id = 2")  # ratios unknown, not 0


def _derived(conn):
    return {r[0]: r[1:] for r in conn.execute(
        """SELECT DISTINCT recipe_id, sat_fat_pct_kcal, sugar_pct_kcal, fiber_per_1000kcal, potassium_mg
           FROM chunk ORDER BY recipe_id""")}


def test_retag_fills_the_derived_nutrition_columns(recipes, fake_embed):
    _set_nutrition(recipes)
    build(recipes)
    tag_test_db(recipes)
    # a partition built before migration 006: the columns exist but are empty
    recipes.execute("UPDATE chunk SET sat_fat_pct_kcal = NULL, sugar_pct_kcal = NULL, fiber_per_1000kcal = NULL, "
                    "potassium_mg = NULL")
    ingest.run(recipes, ["retag", "sentence"])
    d = _derived(recipes)
    assert d[1] == (9.0, 20.0, 15.0, 300.0)  # 4*9/400*100, 20*4/400*100, 6/400*1000
    assert d[2] == (None, None, None, None)  # calories 0: unknown
    recipes.execute("DROP TABLE chunk_sentence_legacy")


def test_a_new_build_computes_the_derived_columns(recipes, fake_embed):
    tag_test_db(recipes)
    _set_nutrition(recipes)
    build(recipes)
    assert _derived(recipes)[1] == (9.0, 20.0, 15.0, 300.0)
