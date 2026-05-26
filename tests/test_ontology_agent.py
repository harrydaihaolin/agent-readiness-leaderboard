"""Tests for the ontology-driven agent architecture."""

import pytest

from scripts.ontology import (
    OntologyDrivenAgent,
    WorkflowStage,
    build_leaderboard_ontology,
)
from scripts.ontology.ontology import OntologyClass, OntologyRegistry, OntologyRelationship
from scripts.ontology.tools import (
    AssumptionLogTool,
    GapCaptureTool,
    QuestionTool,
    ValidationTool,
    WorkflowTool,
)


# ---------------------------------------------------------------------------
# OntologyRegistry
# ---------------------------------------------------------------------------


def test_registry_register_and_retrieve_class():
    registry = OntologyRegistry()
    cls = OntologyClass(name="Foo", description="test", required_fields=["id"])
    registry.register_class(cls)
    assert registry.get_class("Foo") is cls
    assert registry.get_class("Missing") is None


def test_registry_constraints_for_returns_matching_only():
    registry = build_leaderboard_ontology()
    repo_constraints = [c.name for c in registry.constraints_for("Repository")]
    assert "repo_slug_format" in repo_constraints
    score_constraints = [c.name for c in registry.constraints_for("Score")]
    assert "score_range" in score_constraints
    assert "repo_slug_format" not in score_constraints


def test_registry_relationships_from():
    registry = build_leaderboard_ontology()
    rels = {r.name for r in registry.relationships_from("Repository")}
    assert "has_score" in rels
    # Score's relationships should not appear under Repository
    repo_targets = {r.target for r in registry.relationships_from("Repository")}
    assert "Score" in repo_targets


def test_build_leaderboard_ontology_has_all_pillars():
    registry = build_leaderboard_ontology()
    taxonomy = registry.taxonomies.get("agent_readiness_pillars")
    assert taxonomy is not None
    assert set(taxonomy.children) == {
        "cognitive_load",
        "feedback",
        "flow",
        "safety",
        "ontology",
    }


# ---------------------------------------------------------------------------
# GapCaptureTool
# ---------------------------------------------------------------------------


def test_gap_capture_stores_and_retrieves():
    tool = GapCaptureTool()
    tool.capture("slug", "missing owner/name", severity="error")
    tool.capture("stars", "unknown star count")
    gaps = tool.get_gaps()
    assert len(gaps) == 2
    assert gaps[0].field == "slug"
    assert gaps[0].severity == "error"
    assert gaps[1].severity == "warn"


def test_gap_has_errors_true_when_error_present():
    tool = GapCaptureTool()
    tool.capture("x", "ctx", severity="warn")
    assert not tool.has_errors()
    tool.capture("y", "ctx", severity="error")
    assert tool.has_errors()


def test_gap_clear_resets_state():
    tool = GapCaptureTool()
    tool.capture("x", "ctx")
    tool.clear()
    assert tool.get_gaps() == []


# ---------------------------------------------------------------------------
# QuestionTool
# ---------------------------------------------------------------------------


def test_question_tool_generates_message():
    from scripts.ontology.tools import Gap

    qt = QuestionTool()
    gap = Gap(field="slug", context="Slug must be owner/name")
    question = qt.generate(gap)
    assert "slug" in question
    assert "Slug must be owner/name" in question


def test_question_tool_generate_all():
    from scripts.ontology.tools import Gap

    qt = QuestionTool()
    gaps = [Gap("a", "ctx-a"), Gap("b", "ctx-b")]
    questions = qt.generate_all(gaps)
    assert len(questions) == 2


# ---------------------------------------------------------------------------
# AssumptionLogTool
# ---------------------------------------------------------------------------


def test_assumption_log_and_retrieve():
    tool = AssumptionLogTool()
    tool.log("assuming English", 0.9, basis="default locale")
    tool.log("defaulting action to query", 0.5)
    assumptions = tool.get_assumptions()
    assert len(assumptions) == 2
    assert assumptions[0].confidence == pytest.approx(0.9)
    assert assumptions[1].basis == ""


def test_assumption_clear():
    tool = AssumptionLogTool()
    tool.log("x", 0.8)
    tool.clear()
    assert tool.get_assumptions() == []


# ---------------------------------------------------------------------------
# ValidationTool
# ---------------------------------------------------------------------------


def test_validation_passes_valid_repository():
    registry = build_leaderboard_ontology()
    vt = ValidationTool()
    errors = vt.validate({"slug": "owner/repo", "stars": 100}, "Repository", registry)
    assert errors == []


def test_validation_fails_missing_required_field():
    registry = build_leaderboard_ontology()
    vt = ValidationTool()
    errors = vt.validate({}, "Repository", registry)
    assert any("slug" in e for e in errors)


def test_validation_fails_bad_slug_format():
    registry = build_leaderboard_ontology()
    vt = ValidationTool()
    errors = vt.validate({"slug": "no-slash-here"}, "Repository", registry)
    assert any("repo_slug_format" in e for e in errors)


def test_validation_fails_score_out_of_range():
    registry = build_leaderboard_ontology()
    vt = ValidationTool()
    errors = vt.validate({"overall": 150}, "Score", registry)
    assert any("score_range" in e for e in errors)


def test_validation_unknown_class():
    registry = build_leaderboard_ontology()
    vt = ValidationTool()
    errors = vt.validate({"x": 1}, "NonExistent", registry)
    assert any("Unknown class" in e for e in errors)


# ---------------------------------------------------------------------------
# WorkflowTool
# ---------------------------------------------------------------------------


def test_workflow_tool_records_transitions():
    wt = WorkflowTool()
    wt.transition("A", "B", "step 1")
    wt.transition("B", "C")
    history = wt.history()
    assert len(history) == 2
    assert history[0].from_stage == "A"
    assert history[0].to_stage == "B"
    assert history[0].reason == "step 1"
    assert history[1].reason == ""


# ---------------------------------------------------------------------------
# OntologyDrivenAgent — happy path
# ---------------------------------------------------------------------------


def test_agent_happy_path_repository_query():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "query",
            "entity_type": "Repository",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert result.success is True
    assert result.stage == WorkflowStage.OUTPUT
    assert result.errors == []
    assert result.output["action"] == "query"
    assert result.output["entity_type"] == "Repository"


def test_agent_happy_path_score_validate():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "validate",
            "entity_type": "Score",
            "entity": {"overall": 87},
        }
    )
    assert result.success is True
    assert result.stage == WorkflowStage.OUTPUT


# ---------------------------------------------------------------------------
# OntologyDrivenAgent — intent inference
# ---------------------------------------------------------------------------


def test_agent_infers_action_from_text():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "text": "find repos with high scores",
            "entity_type": "Repository",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert result.success is True
    assert result.output["action"] == "query"
    assert any("Inferred action" in a.statement for a in result.assumptions)


def test_agent_defaults_action_when_no_text():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "entity_type": "Repository",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert result.success is True
    assert result.output["action"] == "query"


# ---------------------------------------------------------------------------
# OntologyDrivenAgent — entity type inference
# ---------------------------------------------------------------------------


def test_agent_infers_entity_type_from_slug():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "query",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert result.success is True
    assert result.output["entity_type"] == "Repository"


def test_agent_infers_entity_type_from_overall():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "query",
            "entity": {"overall": 72},
        }
    )
    assert result.success is True
    assert result.output["entity_type"] == "Score"


# ---------------------------------------------------------------------------
# OntologyDrivenAgent — gap handling path
# ---------------------------------------------------------------------------


def test_agent_gap_handling_missing_entity_type():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "query",
            "entity": {"unknown_field": "value"},
        }
    )
    assert result.success is False
    assert result.stage == WorkflowStage.GAP_HANDLING
    assert result.needs_clarification is True
    assert any("entity_type" in q for q in result.questions)


def test_agent_gap_handling_invalid_slug():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "query",
            "entity_type": "Repository",
            "entity": {"slug": "noslash"},
        }
    )
    assert result.success is False
    assert result.errors != []


def test_agent_gap_handling_unknown_action():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)
    result = agent.process(
        {
            "action": "delete",
            "entity_type": "Repository",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert result.success is False
    assert result.stage == WorkflowStage.GAP_HANDLING


# ---------------------------------------------------------------------------
# OntologyDrivenAgent — state reset between calls
# ---------------------------------------------------------------------------


def test_agent_resets_state_between_calls():
    registry = build_leaderboard_ontology()
    agent = OntologyDrivenAgent(registry)

    # First call triggers gap handling
    r1 = agent.process({"action": "query", "entity": {"unknown_field": "x"}})
    assert r1.success is False

    # Second call with valid data should succeed cleanly
    r2 = agent.process(
        {
            "action": "query",
            "entity_type": "Repository",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert r2.success is True
    assert r2.gaps == []


# ---------------------------------------------------------------------------
# OntologyDrivenAgent — knowledge source delegation
# ---------------------------------------------------------------------------


def test_agent_delegates_to_knowledge_source():
    registry = build_leaderboard_ontology()

    class FakeKnowledgeSource:
        def query(self, entity_type: str, entity: dict) -> dict:
            return {"from_ks": True, "entity_type": entity_type}

    agent = OntologyDrivenAgent(registry, knowledge_source=FakeKnowledgeSource())
    result = agent.process(
        {
            "action": "query",
            "entity_type": "Repository",
            "entity": {"slug": "owner/repo"},
        }
    )
    assert result.success is True
    assert result.output == {"from_ks": True, "entity_type": "Repository"}
