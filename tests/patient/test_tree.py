"""MV1: the table-of-contents tree (spec 5.3). Deterministic, no identity, no excluded organizer."""

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from api.patient import ccda, rules
from api.patient.models import Encounter
from api.patient.tree import build_tree

FIXTURE = Path(__file__).parent / "fixtures" / "Barton704_Upton904_887e4b4e-a3e1-b573-4a16-38386d3e0b88.xml"


@pytest.fixture(scope="module")
def record():
    return ccda.read_record(FIXTURE, "sample", rules.load_p7())[0]


@pytest.fixture(scope="module")
def nodes(record):
    return build_tree(record)


def test_root_then_four_fixed_nodes_in_order(nodes):
    assert nodes[0].node_id == "patient:887e4b4e-a3e1-b573-4a16-38386d3e0b88" and nodes[0].kind == "root"
    assert [(n.node_id, n.kind) for n in nodes[1:5]] == [
        ("allergies", "fixed"), ("problems.active", "fixed"), ("meds.active", "fixed"), ("vitals.latest", "fixed")]
    assert all(n.parent_id == nodes[0].node_id for n in nodes[1:])


def test_context_nodes_by_year(nodes):
    context = [n.node_id for n in nodes if n.kind == "context"]
    assert context[0] == "results.2021"  # the CBC; questionnaires never make a node
    assert "encounters.2018" in context and "encounters.2026" in context
    assert not any(c.startswith("results.") and c != "results.2021" for c in context)


def test_a_year_with_no_fact_gets_no_node(record):
    one = replace(record, results=(), encounters=(Encounter("e1", "185349003", "Encounter for check up (procedure)",
                                                            date(2020, 5, 1)),))
    ids = [n.node_id for n in build_tree(one)]
    assert [i for i in ids if "." in i and i.split(".")[0] in {"results", "encounters"}] == ["encounters.2020"]


def test_fixed_nodes_exist_even_when_empty(record):
    empty = replace(record, allergies=(), problems=(), medications=(), vitals=(), results=(), encounters=())
    nodes = build_tree(empty)
    assert [n.node_id for n in nodes[1:]] == ["allergies", "problems.active", "meds.active", "vitals.latest"]
    assert all(n.facts == [] for n in nodes[1:])


def test_entry_ids_point_at_the_source_entries(nodes):
    allergies = next(n for n in nodes if n.node_id == "allergies")
    assert "887e4b4e-a3e1-b573-e91f-98d891253e61" in allergies.entry_ids  # the wheat allergy act
    assert len(allergies.entry_ids) == len(allergies.facts) == 8


def test_deterministic(record, nodes):
    assert build_tree(record) == nodes


def test_no_identity_and_no_excluded_organizer(nodes):
    text = json.dumps([n.__dict__ for n in nodes], default=str)
    for word in ["Barton704", "Upton904", "raceCode", "PHQ", "GAD-7", "DAST", "AUDIT"]:
        assert word not in text, word
    excluded = set(rules.load_p7().exclude_loinc)
    for n in nodes:
        for f in n.facts:
            assert f.get("loinc") not in excluded
