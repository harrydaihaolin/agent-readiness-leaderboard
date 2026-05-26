"""Workflow stage definitions and result envelope."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from .tools import Assumption, Gap


class WorkflowStage(Enum):
    REQUEST = auto()
    INTENT = auto()
    MAPPING = auto()
    VALIDATION = auto()
    GAP_HANDLING = auto()
    EXECUTION = auto()
    OUTPUT = auto()


@dataclass
class WorkflowResult:
    """Envelope returned by OntologyDrivenAgent.process()."""

    stage: WorkflowStage
    success: bool
    output: Any = None
    gaps: list[Gap] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.questions) or bool(self.gaps)
