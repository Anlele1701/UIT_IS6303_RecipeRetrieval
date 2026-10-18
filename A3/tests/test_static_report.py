import json

import pytest

import static_report


def test_the_committed_report_html_is_built_from_the_bundle_as_it_is_now():
    """Fails when ui/public/report.json or the template changed after report.html was built.

    Rebuild with `uv run python scripts/static_report.py`.
    """
    if not static_report.OUT.exists():
        pytest.fail(f"{static_report.OUT} is missing; build it with scripts/static_report.py")
    bundle = json.loads(static_report.BUNDLE.read_text(encoding="utf-8"))
    assert static_report.OUT.read_text(encoding="utf-8") == static_report.render(bundle), \
        "report.html is stale; rebuild it with scripts/static_report.py"


def test_the_page_embeds_only_what_it_draws():
    bundle = json.loads(static_report.BUNDLE.read_text(encoding="utf-8"))
    data = static_report.page_data(bundle)
    assert "per_query" not in data and "recipes" not in data
    assert data["run"]["queries"] == len(json.loads(json.dumps(bundle["queries"])))
