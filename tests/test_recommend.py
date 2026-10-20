"""/recommend: the pipeline with a fake search, fake recipe rows and a fake LLM, plus the route and the LLM client."""

from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import ConnectionPool

from api import allergens, config, dietary_rules, llm, recommend, retrieval
from api.main import app

P = {n: UUID(int=n) for n in range(1, 8)}  # the mini cohort; see test_patients.py
RULES = dietary_rules.load_rules(config.RULES_PATH)
BOOK = allergens.load_allergens(config.ALLERGENS_PATH)


def hit(chunk_id, recipe_id, content="Soup\nA bowl of soup."):
    return retrieval.Candidate(chunk_id, recipe_id, "directions", 0, content, 1.0, 1, 2, 0.03, 0.9)


def recipe_row(title, sodium, ingredients=("1 cup water",), **extra):
    nutrition = {"calories": 200.0, "protein_g": 10.0, "fat_g": 5.0, "saturated_fat_g": 1.0,
                 "carbohydrates_g": 30.0, "sugars_g": 4.0, "sodium_mg": sodium} | extra
    return {"title": title, "category": "Soup", "url": f"http://x/{title}", "rating": 4.5, "total_minutes": 30,
            "servings": 4, "nutrition": nutrition, "ingredients": list(ingredients)}


class Fakes:
    """Stands in for the search, the recipe lookup and the LLM, and remembers how they were called."""

    def __init__(self, hits, rows, answer="Soup (1) has 120 mg sodium."):
        self.hits, self.rows, self.answer = hits, rows, answer
        self.params = self.messages = self.columns = None

    def search(self, conn, params, qvec, scorer):
        self.params = params
        return self.hits

    def fetch(self, conn, ids, columns):
        self.columns = columns
        return {i: self.rows[i] for i in ids if i in self.rows}

    def explain(self, messages):
        self.messages = messages
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def run(ehr, fakes, patient=2, explain=True, k=5, strategy="semantic", book=BOOK):
    req = recommend.RecommendRequest(patient_id=P[patient], query="soup", strategy=strategy, k=k, explain=explain)
    return recommend.recommend(ehr, req, rules=RULES, allergen_book=book, embed=lambda t: "[0.1]", scorer=None,
                               explain=fakes.explain, search=fakes.search, fetch=fakes.fetch)


# --- pure steps ---------------------------------------------------------------------------


def test_chunks_are_grouped_by_recipe_keeping_the_best_chunk_in_rank_order():
    grouped = recommend.group_recipes([hit(10, 1), hit(11, 2), hit(12, 1), hit(13, 3)])
    assert [(c.recipe_id, c.chunk_id) for c in grouped] == [(1, 10), (2, 11), (3, 13)]


def test_columns_read_are_the_display_ones_plus_the_filtered_ones_and_never_unknown_names():
    cols = recommend.nutrient_columns({"max_sodium_mg": 500.0, "max_bogus; DROP TABLE x": 1.0})
    assert "sodium_mg" in cols and len(cols) == len(set(cols)) and all(c in dietary_rules.NUTRIENTS for c in cols)


def test_a_missing_value_fails_the_check():
    checks = recommend.nutrition_checks({"sodium_mg": None, "carbohydrates_g": 30.0},
                                        {"max_sodium_mg": 500.0, "max_carbohydrates_g": 60.0})
    assert [(c.nutrient, c.ok) for c in checks] == [("sodium_mg", False), ("carbohydrates_g", True)]


def test_numbers_the_llm_made_up_are_reported_and_known_ones_are_not():
    plan = SimpleNamespace(evidence=[SimpleNamespace(per_serving=500.0, daily=1500.0)], unapplied_limits=[])
    r = SimpleNamespace(nutrition={"sodium_mg": 120.0, "fat_g": 5.5}, servings=4, rating=4.5, rank=1,
                        total_minutes=30)
    answer = "Recipe 1 has 120 mg sodium, 5.5 g fat, well under 500 mg; it serves 4 and takes 30 minutes, 1,500 daily, 999 mg."
    assert recommend.unverified_numbers(answer, plan, [r]) == ["999"]


# --- the pipeline ---------------------------------------------------------------------------


def test_filters_reach_the_search_and_a_good_recipe_comes_back_explained(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Light Soup", 120.0)})
    out = run(ehr, fakes)
    assert fakes.params.max_sodium_mg == 500.0 and fakes.params.k == config.RECOMMEND_CHUNKS
    assert [r.recipe_id for r in out.recipes] == [7]
    assert out.recipes[0].checks[0].ok and out.recipes[0].checks[0].limit == 500.0
    assert out.recipes[0].best_chunk.text == "A bowl of soup." and out.recipes[0].rank == 1
    assert out.answer == "Soup (1) has 120 mg sodium." and out.answer_error is None and out.unverified_numbers == []
    assert "sodium_mg <= 500.0" in fakes.messages[1]["content"] and "Light Soup" in fakes.messages[1]["content"]
    assert {"profile", "rules", "embed", "search", "assemble", "explain", "total"} <= set(out.timings_ms)


def test_a_recipe_that_breaks_a_limit_is_dropped_and_never_shown_or_explained(ehr):
    fakes = Fakes([hit(1, 7), hit(2, 8), hit(3, 9)],
                  {7: recipe_row("Salty", 900.0), 8: recipe_row("Unknown", None), 9: recipe_row("Light", 100.0)})
    out = run(ehr, fakes)
    assert [r.recipe_id for r in out.recipes] == [9] and out.dropped_by_nutrition_check == [7, 8]
    assert "Salty" not in fakes.messages[1]["content"]
    assert any("re-check" in w for w in out.warnings)


def test_filters_are_not_relaxed_when_nothing_qualifies(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Salty", 900.0)})
    out = run(ehr, fakes)
    assert out.recipes == [] and out.answer is None and fakes.messages is None  # the LLM is not asked
    assert any("relaxed" in w for w in out.warnings)


def test_no_hits_is_an_empty_answer_not_an_error(ehr):
    out = run(ehr, Fakes([], {}))
    assert out.recipes == [] and out.answer is None


def test_only_k_recipes_are_returned_in_rank_order(ehr):
    rows = {i: recipe_row(f"R{i}", 100.0) for i in range(1, 7)}
    out = run(ehr, Fakes([hit(i, i) for i in range(1, 7)], rows), k=3)
    assert [r.recipe_id for r in out.recipes] == [1, 2, 3]


def test_an_llm_failure_keeps_the_recipes(ehr):
    out = run(ehr, Fakes([hit(1, 7)], {7: recipe_row("Light", 100.0)}, answer=llm.LLMError("Ollama is down")))
    assert [r.recipe_id for r in out.recipes] == [7] and out.answer is None and out.answer_error == "Ollama is down"


def test_explain_false_does_not_call_the_llm(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Light", 100.0)})
    out = run(ehr, fakes, explain=False)
    assert fakes.messages is None and out.answer is None and out.answer_error is None


def test_an_invented_number_is_flagged_in_the_response(ehr):
    out = run(ehr, Fakes([hit(1, 7)], {7: recipe_row("Light", 100.0)}, answer="It has only 42 mg of sodium."))
    assert out.unverified_numbers == ["42"] and any("42" in w for w in out.warnings)


def test_a_patient_without_applicable_rules_searches_unfiltered_but_says_so(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Soup", 5000.0)})
    out = run(ehr, fakes, patient=4)
    assert fakes.params.max_sodium_mg is None and [r.recipe_id for r in out.recipes] == [7]
    assert any("No dietary Filter applies" in w for w in out.warnings)


def test_limits_that_could_not_be_applied_and_unsupported_conditions_are_warned_about(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Soup", 100.0, carbohydrates_g=10.0)})
    out = run(ehr, fakes, patient=7)
    assert fakes.params.max_carbohydrates_g == 60.0
    assert any("saturated_fat_g" in w for w in out.warnings)
    assert any("kidney" in w.lower() for w in out.warnings)


def test_unknown_patient(ehr):
    with pytest.raises(recommend.patients.PatientNotFound):
        recommend.recommend(ehr, recommend.RecommendRequest(patient_id=UUID(int=999), query="x", strategy="s"),
                            rules=RULES, allergen_book=BOOK, embed=None, scorer=None, explain=None)


# --- allergies ------------------------------------------------------------------------------
# Mini cohort: patient 1 is allergic to eggs (and had a peanut allergy that stopped); patient 4 to shellfish.


def test_a_recipe_with_the_patients_allergen_is_removed_whatever_its_rank(ehr):
    fakes = Fakes([hit(1, 7), hit(2, 8), hit(3, 9)],
                  {7: recipe_row("Quiche", 100.0, ["3 large eggs", "1 cup flour"]),
                   8: recipe_row("Eggplant Stew", 100.0, ["1 eggplant"]),
                   9: recipe_row("Shrimp Bowl", 100.0, ["1 lb shrimp"])})
    out = run(ehr, fakes, patient=1)
    assert [r.recipe_id for r in out.recipes] == [8, 9]  # eggplant is not egg; shrimp is not this patient's allergen
    assert [(e.recipe_id, e.allergen, e.matched, e.where) for e in out.allergy_check.excluded] == [
        (7, "Egg", "eggs", "3 large eggs")]
    assert out.allergy_check.checked == ["Egg"] and out.allergy_check.unchecked == []
    assert any("allergic" in w and "Egg" in w for w in out.warnings)
    assert "Quiche" not in fakes.messages[1]["content"]


def test_the_title_counts_too(ehr):
    out = run(ehr, Fakes([hit(1, 7)], {7: recipe_row("Egg Salad", 100.0, ["1 cup lettuce"])}), patient=1)
    assert out.recipes == [] and out.allergy_check.excluded[0].where == "title"


def test_a_stopped_allergy_is_not_screened(ehr):
    out = run(ehr, Fakes([hit(1, 7)], {7: recipe_row("Peanut Soup", 100.0, ["1 cup peanuts"])}), patient=1)
    assert [r.recipe_id for r in out.recipes] == [7]  # the peanut allergy of patient 1 stopped in 2000


def test_a_patient_without_food_allergies_screens_nothing(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Quiche", 5.0, ["3 eggs"])})
    out = run(ehr, fakes, patient=3)
    assert [r.recipe_id for r in out.recipes] == [7] and out.allergy_check.checked == []
    assert fakes.params.k == config.RECOMMEND_CHUNKS


def test_screening_asks_the_search_for_more_chunks_so_removed_recipes_still_leave_k(ehr):
    fakes = Fakes([hit(1, 7)], {7: recipe_row("Soup", 100.0)})
    run(ehr, fakes, patient=1)
    assert fakes.params.k == config.MAX_K


def test_removed_recipes_make_room_for_the_next_ones_up_to_k(ehr):
    rows = {i: recipe_row(f"R{i}", 100.0, ["2 eggs"] if i <= 4 else ["1 cup rice"]) for i in range(1, 8)}
    out = run(ehr, Fakes([hit(i, i) for i in range(1, 8)], rows), patient=1, k=3)
    assert [r.recipe_id for r in out.recipes] == [5, 6, 7]


def test_a_recipe_with_no_ingredient_lines_cannot_be_cleared(ehr):
    out = run(ehr, Fakes([hit(1, 7)], {7: recipe_row("Mystery", 100.0, [])}), patient=1)
    assert out.recipes == [] and out.allergy_check.excluded[0].where == "no ingredient lines to check"


def test_a_food_allergy_without_a_keyword_list_is_reported_not_ignored(ehr):
    only_fish = allergens.parse_allergens({"version": 1, "allergens": [
        {"name": "Fish", "snomed_codes": ["735971005"], "terms": ["fish"]}]})
    out = run(ehr, Fakes([hit(1, 7)], {7: recipe_row("Quiche", 100.0, ["3 eggs"])}), patient=1, book=only_fish)
    assert out.allergy_check.unchecked == ["Eggs (edible) (substance)"] and out.allergy_check.checked == []
    assert any("cannot be screened" in w for w in out.warnings)


def test_allergy_and_nutrition_failures_are_reported_separately(ehr):
    fakes = Fakes([hit(1, 7), hit(2, 8)], {7: recipe_row("Eggy", 900.0, ["2 eggs"]), 8: recipe_row("Salty", 900.0)})
    out = run(ehr, fakes, patient=1)
    assert [e.recipe_id for e in out.allergy_check.excluded] == [7] and out.dropped_by_nutrition_check == [8]


# --- the route ------------------------------------------------------------------------------


@pytest.fixture
def client(ehr_db_url, ehr, monkeypatch):
    app.state.pool = ConnectionPool(ehr_db_url, min_size=1, max_size=2, open=True)
    app.state.rules = RULES
    app.state.allergens = BOOK
    app.state.http = object()
    app.state.reranker = SimpleNamespace(score=lambda q, texts: [0.0] * len(texts))
    monkeypatch.setattr("api.main.strategies.registry", lambda conn: {})
    monkeypatch.setattr("api.main.strategies.strategy_problem", lambda name, reg: None if name == "semantic" else "no")
    monkeypatch.setattr("api.main.embed_query", lambda http, text: "[0.1]")
    monkeypatch.setattr("api.main.llm.chat", lambda http, messages: "Light Soup has 120 mg sodium.")
    monkeypatch.setattr("api.recommend.retrieval.hybrid", lambda conn, params, qvec, scorer: [hit(1, 7)])
    monkeypatch.setattr("api.recommend.fetch_recipes",
                        lambda conn, ids, cols: {7: recipe_row("Light Soup", 120.0)})
    yield TestClient(app)
    app.state.pool.close()


def body(**over):
    return {"patient_id": str(P[2]), "query": "soup", "strategy": "semantic"} | over


def test_route_returns_the_whole_response(client):
    r = client.post("/recommend", json=body())
    assert r.status_code == 200
    out = r.json()
    assert out["patient"]["display_name"] and out["diet_plan"]["filters"] == {"max_sodium_mg": 500.0}
    assert out["recipes"][0]["title"] == "Light Soup" and out["answer"].startswith("Light Soup")


def test_route_errors(client, monkeypatch):
    assert client.post("/recommend", json=body(patient_id=str(UUID(int=999)))).status_code == 404
    assert client.post("/recommend", json=body(patient_id="nope")).status_code == 422
    assert client.post("/recommend", json=body(strategy="other")).status_code == 422
    assert client.post("/recommend", json=body(query="")).status_code == 422
    assert client.post("/recommend", json=body(k=config.RECOMMEND_MAX_K + 1)).status_code == 422
    assert client.post("/recommend", json=body(surprise=1)).status_code == 422

    def down(http, text):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr("api.main.embed_query", down)
    assert client.post("/recommend", json=body()).status_code == 503


def test_route_survives_an_llm_outage(client, monkeypatch):
    def down(http, messages):
        raise llm.LLMError("Ollama is not reachable")
    monkeypatch.setattr("api.main.llm.chat", down)
    out = client.post("/recommend", json=body()).json()
    assert out["answer"] is None and "not reachable" in out["answer_error"] and len(out["recipes"]) == 1


# --- fetch_recipes against the real schema ----------------------------------------------------


def test_fetch_recipes_reads_details_nutrition_and_ingredients_in_order(recipes):
    recipes.execute("UPDATE recipe_nutrition SET sodium_mg = 77 WHERE recipe_id = 1")
    out = recommend.fetch_recipes(recipes, [1, 2], ["calories", "sodium_mg"])
    assert set(out) == {1, 2} and out[1]["title"] == "Garlic Shrimp" and out[1]["category"] == "Main"
    assert out[1]["nutrition"] == {"calories": 100.0, "sodium_mg": 77.0} and out[2]["nutrition"]["sodium_mg"] is None
    assert out[1]["ingredients"] == ["1 lb shrimp", "4 cloves garlic"]
    assert recommend.fetch_recipes(recipes, [], ["calories"]) == {}


# --- the LLM client -------------------------------------------------------------------------


def chat_with(handler, **kw):
    return llm.chat(httpx.Client(transport=httpx.MockTransport(handler)), [{"role": "user", "content": "hi"}], **kw)


def test_chat_returns_the_reply_and_sends_the_model_and_messages():
    seen = {}

    def handler(request):
        seen.update(httpx.Response(200, content=request.content).json())
        return httpx.Response(200, json={"message": {"content": "hello"}})
    assert chat_with(handler, json_mode=True) == "hello"
    assert seen["model"] == config.LLM_MODEL and seen["stream"] is False and seen["format"] == "json"


def test_chat_retries_a_server_error_once_but_not_a_client_error():
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json={"message": {"content": "ok"}})
    assert chat_with(flaky) == "ok" and len(calls) == 2

    calls.clear()

    def missing(request):
        calls.append(1)
        return httpx.Response(404, text="model not found")
    with pytest.raises(llm.LLMError, match="404"):
        chat_with(missing)
    assert len(calls) == 1


def test_chat_reports_an_unreachable_server_and_empty_or_garbled_replies():
    def refuse(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(llm.LLMError, match="not reachable"):
        chat_with(refuse)
    with pytest.raises(llm.LLMError, match="empty"):
        chat_with(lambda r: httpx.Response(200, json={"message": {"content": "  "}}))
    with pytest.raises(llm.LLMError, match="cannot read"):
        chat_with(lambda r: httpx.Response(200, json={"oops": 1}))
