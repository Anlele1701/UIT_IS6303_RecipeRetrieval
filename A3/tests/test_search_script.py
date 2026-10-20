import pytest

from search import parse_args, search


class RecordingConn:
    def execute(self, sql, params):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return []


def test_search_script_refuses_to_run_without_a_strategy():
    with pytest.raises(SystemExit):
        parse_args(["bm25", "garlic shrimp"])


def test_search_script_scopes_the_query_to_the_given_strategy():
    a = parse_args(["bm25", "garlic shrimp", "--strategy", "fixed", "--kind", "step"])
    conn = RecordingConn()
    search(conn, a.method, a.query, a.strategy, kind=a.kind)
    assert "strategy = %s AND kind = %s" in conn.sql
    assert conn.params == ["garlic shrimp", "fixed", "step", 10]
