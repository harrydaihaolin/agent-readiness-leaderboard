"""Agent tooling layer: gap capture, questions, assumptions, validation, workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ontology import OntologyRegistry


@dataclass
class Gap:
    field: str
    context: str
    severity: str = "warn"


@dataclass
class Assumption:
    statement: str
    confidence: float  # 0.0–1.0
    basis: str = ""


@dataclass
class WorkflowTransition:
    from_stage: str
    to_stage: str
    reason: str = ""


class GapCaptureTool:
    """Records missing or ambiguous information encountered during processing."""

    def __init__(self) -> None:
        self._gaps: list[Gap] = []

    def capture(self, field: str, context: str, severity: str = "warn") -> Gap:
        gap = Gap(field=field, context=context, severity=severity)
        self._gaps.append(gap)
        return gap

    def get_gaps(self) -> list[Gap]:
        return list(self._gaps)

    def clear(self) -> None:
        self._gaps.clear()

    def has_errors(self) -> bool:
        return any(g.severity == "error" for g in self._gaps)


class QuestionTool:
    """Generates clarifying questions from captured gaps."""

    def generate(self, gap: Gap) -> str:
        return f"Please provide '{gap.field}': {gap.context}"

    def generate_all(self, gaps: list[Gap]) -> list[str]:
        return [self.generate(g) for g in gaps]


class AssumptionLogTool:
    """Logs assumptions made when context is inferred rather than explicit."""

    def __init__(self) -> None:
        self._assumptions: list[Assumption] = []

    def log(self, statement: str, confidence: float, basis: str = "") -> Assumption:
        a = Assumption(statement=statement, confidence=confidence, basis=basis)
        self._assumptions.append(a)
        return a

    def get_assumptions(self) -> list[Assumption]:
        return list(self._assumptions)

    def clear(self) -> None:
        self._assumptions.clear()


class ValidationTool:
    """Validates entity dicts against ontology constraints."""

    def validate(
        self,
        entity: dict[str, Any],
        class_name: str,
        registry: OntologyRegistry,
    ) -> list[str]:
        errors: list[str] = []
        cls = registry.get_class(class_name)
        if cls is None:
            errors.append(f"Unknown class '{class_name}'")
            return errors
        for req_field in cls.required_fields:
            if req_field not in entity or entity[req_field] is None:
                errors.append(
                    f"Required field '{req_field}' missing for {class_name}"
                )
        for constraint in registry.constraints_for(class_name):
            try:
                if not constraint.validate(entity):
                    errors.append(
                        f"Constraint '{constraint.name}' failed: "
                        f"{constraint.description}"
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Constraint '{constraint.name}' raised: {exc}")
        return errors


class WorkflowTool:
    """Tracks workflow stage transitions."""

    def __init__(self) -> None:
        self._history: list[WorkflowTransition] = []

    def transition(
        self, from_stage: str, to_stage: str, reason: str = ""
    ) -> WorkflowTransition:
        t = WorkflowTransition(
            from_stage=from_stage, to_stage=to_stage, reason=reason
        )
        self._history.append(t)
        return t

    def history(self) -> list[WorkflowTransition]:
        return list(self._history)


# Re-export so callers can do `from scripts.ontology.tools import Gap, Assumption`
__all__ = [
    "Assumption",
    "AssumptionLogTool",
    "Gap",
    "GapCaptureTool",
    "QuestionTool",
    "ValidationTool",
    "WorkflowTool",
    "WorkflowTransition",
]
