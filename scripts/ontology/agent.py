"""Ontology-Driven Agent.

Implements the workflow from the architecture diagram:

  User Request
    → Intent Understanding
    → Ontology Mapping  (entities / terms / relationships)
    → Validation & Reasoning  (rules / constraints / required fields)
    → Complete Context?
        Yes → Action Execute → Output
        No  → Gap Handling (capture → question → assumption → escalate)
"""

from __future__ import annotations

from typing import Any

from .ontology import OntologyRegistry
from .tools import (
    AssumptionLogTool,
    GapCaptureTool,
    QuestionTool,
    ValidationTool,
    WorkflowTool,
)
from .workflow import WorkflowResult, WorkflowStage

_VALID_ACTIONS: frozenset[str] = frozenset({"query", "validate", "rank", "summarize"})

_KEYWORD_TO_ACTION: dict[str, str] = {
    "get": "query",
    "find": "query",
    "list": "query",
    "show": "query",
    "validate": "validate",
    "check": "validate",
    "rank": "rank",
    "top": "rank",
    "summarize": "summarize",
    "summary": "summarize",
}


class OntologyDrivenAgent:
    """Processes requests using ontology-grounded reasoning.

    Parameters
    ----------
    registry:
        Pre-built OntologyRegistry (use ``build_leaderboard_ontology()`` for
        the default agent-readiness domain).
    knowledge_source:
        Optional object that exposes callable attributes matching action names
        (``query``, ``validate``, ``rank``, ``summarize``).  When provided,
        the agent delegates execution to it instead of returning a dry summary.
    """

    def __init__(
        self,
        registry: OntologyRegistry,
        knowledge_source: Any | None = None,
    ) -> None:
        self.registry = registry
        self.knowledge_source = knowledge_source
        self.gap_tool = GapCaptureTool()
        self.question_tool = QuestionTool()
        self.assumption_tool = AssumptionLogTool()
        self.validation_tool = ValidationTool()
        self.workflow_tool = WorkflowTool()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process(self, request: dict[str, Any]) -> WorkflowResult:
        """Execute the full ontology-driven workflow for *request*.

        Returns a :class:`WorkflowResult` whose ``success`` flag indicates
        whether execution reached the OUTPUT stage.  When ``success`` is
        ``False`` the caller should inspect ``gaps``, ``questions``, and
        ``errors`` to understand what information is missing.
        """
        self._reset_state()
        self.workflow_tool.transition("START", WorkflowStage.REQUEST.name)

        # 1 — Intent Understanding
        intent = self._understand_intent(request)
        self.workflow_tool.transition(
            WorkflowStage.REQUEST.name, WorkflowStage.INTENT.name
        )

        # 2 — Ontology Mapping
        mapped = self._map_to_ontology(request, intent)
        self.workflow_tool.transition(
            WorkflowStage.INTENT.name, WorkflowStage.MAPPING.name
        )

        # 3 — Validation & Reasoning
        errors = self._validate(mapped)
        self.workflow_tool.transition(
            WorkflowStage.MAPPING.name, WorkflowStage.VALIDATION.name
        )

        # 4 — Completeness check
        gaps = self.gap_tool.get_gaps()
        if errors or gaps:
            self.workflow_tool.transition(
                WorkflowStage.VALIDATION.name,
                WorkflowStage.GAP_HANDLING.name,
                "incomplete or invalid context",
            )
            questions = self.question_tool.generate_all(gaps)
            return WorkflowResult(
                stage=WorkflowStage.GAP_HANDLING,
                success=False,
                gaps=gaps,
                assumptions=self.assumption_tool.get_assumptions(),
                questions=questions,
                errors=errors,
            )

        # 5 — Execute
        self.workflow_tool.transition(
            WorkflowStage.VALIDATION.name,
            WorkflowStage.EXECUTION.name,
            "context complete",
        )
        output = self._execute(intent, mapped)

        # 6 — Output
        self.workflow_tool.transition(
            WorkflowStage.EXECUTION.name, WorkflowStage.OUTPUT.name
        )
        return WorkflowResult(
            stage=WorkflowStage.OUTPUT,
            success=True,
            output=output,
            assumptions=self.assumption_tool.get_assumptions(),
        )

    # ------------------------------------------------------------------
    # Workflow steps (private)
    # ------------------------------------------------------------------

    def _understand_intent(self, request: dict[str, Any]) -> dict[str, Any]:
        action = request.get("action", "")
        if not action:
            text = str(request.get("text", "")).lower()
            for keyword, mapped_action in _KEYWORD_TO_ACTION.items():
                if keyword in text:
                    action = mapped_action
                    self.assumption_tool.log(
                        f"Inferred action '{action}' from keyword '{keyword}' in text",
                        confidence=0.7,
                        basis="keyword match",
                    )
                    break
        if not action:
            action = "query"
            self.assumption_tool.log(
                "No action detected; defaulting to 'query'",
                confidence=0.5,
                basis="default fallback",
            )
        if action not in _VALID_ACTIONS:
            self.gap_tool.capture(
                field="action",
                context=(
                    f"'{action}' is not a recognised action. "
                    f"Expected one of: {sorted(_VALID_ACTIONS)}"
                ),
                severity="error",
            )
        return {"action": action, "raw": request}

    def _map_to_ontology(
        self,
        request: dict[str, Any],
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        entity_type = request.get("entity_type", "")
        entity = request.get("entity", {})

        if not entity_type:
            if "slug" in entity:
                entity_type = "Repository"
                self.assumption_tool.log(
                    "Inferred entity_type='Repository' from 'slug' field",
                    confidence=0.85,
                    basis="field inference",
                )
            elif "overall" in entity:
                entity_type = "Score"
                self.assumption_tool.log(
                    "Inferred entity_type='Score' from 'overall' field",
                    confidence=0.85,
                    basis="field inference",
                )
            else:
                self.gap_tool.capture(
                    field="entity_type",
                    context="Cannot determine entity type from request fields",
                    severity="error",
                )

        cls = self.registry.get_class(entity_type) if entity_type else None
        relationships = (
            self.registry.relationships_from(entity_type) if entity_type else []
        )

        return {
            "entity_type": entity_type,
            "entity": entity,
            "ontology_class": cls,
            "relationships": relationships,
            "intent": intent,
        }

    def _validate(self, mapped: dict[str, Any]) -> list[str]:
        entity_type = mapped.get("entity_type", "")
        entity = mapped.get("entity", {})
        if not entity_type or not entity:
            return []
        return self.validation_tool.validate(entity, entity_type, self.registry)

    def _execute(
        self,
        intent: dict[str, Any],
        mapped: dict[str, Any],
    ) -> Any:
        action = intent["action"]
        entity = mapped["entity"]
        entity_type = mapped["entity_type"]

        if self.knowledge_source is not None and hasattr(self.knowledge_source, action):
            return getattr(self.knowledge_source, action)(entity_type, entity)

        return {
            "action": action,
            "entity_type": entity_type,
            "entity": entity,
            "relationships": [
                {
                    "name": r.name,
                    "target": r.target,
                    "cardinality": r.cardinality,
                }
                for r in mapped.get("relationships", [])
            ],
        }

    def _reset_state(self) -> None:
        self.gap_tool.clear()
        self.assumption_tool.clear()
        self.workflow_tool = WorkflowTool()
