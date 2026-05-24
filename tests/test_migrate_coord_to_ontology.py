import json
import tempfile
from pathlib import Path

from scripts.migrate_coord_to_ontology import _add_alias, migrate_file


def test_add_alias_skips_when_missing():
    entry = {"pillar_scores": {}}
    assert _add_alias(entry) is False


def test_add_alias_copies_coordination_to_ontology():
    entry = {"pillar_scores": {"coordination": 88}}
    assert _add_alias(entry) is True
    assert entry["pillar_scores"]["ontology"] == 88


def test_add_alias_idempotent():
    entry = {"pillar_scores": {"coordination": 88, "ontology": 88}}
    assert _add_alias(entry) is False
