"""A3 must never point at A1's database: its compose project, volume, container or port."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A1_MARKERS = ["is603_recipe-pgdata", "recipe-pgdata:", "recipe-paradedb", "5434"]
FILES = ["docker-compose.yml", "api/config.py", "scripts/ingest.py", "scripts/make_queries.py", "tests/conftest.py"]


def test_compose_uses_its_own_project_volume_container_and_port():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "name: is603a3" in compose
    assert "a3-pgdata:/var/lib/postgresql/data" in compose
    assert "container_name: a3-paradedb" in compose
    assert '"5435:5432"' in compose


def code(name: str) -> str:
    """The file without its # comments, which may name A1 to explain the split."""
    return "\n".join(line.split("#", 1)[0] for line in (ROOT / name).read_text(encoding="utf-8").splitlines())


def test_no_file_refers_to_the_a1_database():
    for name in FILES:
        text = code(name)
        for marker in A1_MARKERS:
            assert marker not in text, f"{name} mentions {marker}"
