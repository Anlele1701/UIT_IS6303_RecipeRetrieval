import evaluate_ehr_retrieval as ev


def test_score_counts_hits_leaks_and_exact_matches():
    r = ev.score({"a", "b", "x"}, {"a", "b", "c"}, {"x", "y"})
    assert r == {"truth_n": 3, "stale_n": 2, "predicted_n": 3, "tp": 2, "leak": 1, "exact": False}
    assert ev.score({"a"}, {"a"}, set())["exact"] is True


def test_strata_are_terciles_of_document_length():
    s = ev.strata_by_length({str(i): 100 * i for i in range(1, 10)})
    assert [s[str(i)] for i in range(1, 10)] == ["short"] * 3 + ["medium"] * 3 + ["long"] * 3


def test_pick_patients_is_stratified_seeded_and_never_picks_more_than_exist():
    strata = ev.strata_by_length({str(i): i for i in range(30)})
    a = ev.pick_patients(strata, 4, seed=1)
    assert a == ev.pick_patients(strata, 4, seed=1) and len(a) == 12
    assert [strata[p] for p in a] == ["short"] * 4 + ["medium"] * 4 + ["long"] * 4
    assert len(ev.pick_patients(strata, 99, seed=1)) == 30


def row(tp, truth_n, predicted_n, leak=0, error=None, exact=False, **kw):
    return {"tp": tp, "truth_n": truth_n, "predicted_n": predicted_n, "leak": leak, "error": error, "exact": exact,
            "stale_n": 1, "chars_read": 100, "share_of_doc": 0.1, "llm_calls": 2, "ms": 10.0, **kw}


def test_summaries_pool_codes_and_leave_failed_patients_out_of_the_rates():
    out = ev.summarize([row(2, 2, 3, leak=1, exact=False), row(1, 2, 1, exact=False),
                        row(0, 0, 0, error="boom"), row(2, 2, 2, exact=True, rejected_n=1)])
    assert out["patients"] == 4 and out["errors"] == 1
    assert out["recall"] == round(5 / 6, 3) and out["precision"] == round(5 / 6, 3)
    assert out["exact"] == round(1 / 3, 3) and out["leak_patients"] == round(1 / 3, 3)
    assert out["leak_codes"] == 1 and out["invented_codes"] == 1


def test_summaries_of_nothing_do_not_divide_by_zero():
    out = ev.summarize([row(0, 0, 0, error="x")])
    assert out["recall"] is None and out["precision"] is None and out["exact"] is None
    assert ev.summarize_retrieval([row(0, 0, 0, leak=0, exact=True)])["active_seen"] is None
