"""Ontology layer: classes, relationships, taxonomies, constraints, and rules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OntologyClass:
    name: str
    description: str
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)


@dataclass
class OntologyRelationship:
    name: str
    source: str
    target: str
    cardinality: str  # "one-to-one" | "one-to-many" | "many-to-many"


@dataclass
class Taxonomy:
    name: str
    parent: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass
class Constraint:
    name: str
    applies_to: str
    description: str
    validate: Callable[[dict[str, Any]], bool]


@dataclass
class Rule:
    name: str
    condition: str
    action: str
    apply: Callable[[dict[str, Any]], dict[str, Any]] | None = None


class OntologyRegistry:
    """Central registry for all ontology concepts."""

    def __init__(self) -> None:
        self.classes: dict[str, OntologyClass] = {}
        self.relationships: list[OntologyRelationship] = []
        self.taxonomies: dict[str, Taxonomy] = {}
        self.constraints: list[Constraint] = []
        self.rules: list[Rule] = []

    def register_class(self, cls: OntologyClass) -> None:
        self.classes[cls.name] = cls

    def register_relationship(self, rel: OntologyRelationship) -> None:
        self.relationships.append(rel)

    def register_taxonomy(self, taxonomy: Taxonomy) -> None:
        self.taxonomies[taxonomy.name] = taxonomy

    def register_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)

    def register_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def get_class(self, name: str) -> OntologyClass | None:
        return self.classes.get(name)

    def constraints_for(self, class_name: str) -> list[Constraint]:
        return [c for c in self.constraints if c.applies_to == class_name]

    def relationships_from(self, source: str) -> list[OntologyRelationship]:
        return [r for r in self.relationships if r.source == source]


def build_leaderboard_ontology() -> OntologyRegistry:
    """Return an OntologyRegistry pre-populated with agent-readiness domain concepts."""
    registry = OntologyRegistry()

    registry.register_class(
        OntologyClass(
            name="Repository",
            description="A GitHub repository assessed for agent-readiness",
            required_fields=["slug"],
            optional_fields=["stars", "last_scanned", "description"],
        )
    )
    registry.register_class(
        OntologyClass(
            name="Score",
            description="The agent-readiness score for a repository",
            required_fields=["overall"],
            optional_fields=["scanned_at", "tool_version"],
        )
    )
    registry.register_class(
        OntologyClass(
            name="Pillar",
            description=(
                "A scoring dimension "
                "(cognitive_load, feedback, flow, safety, ontology)"
            ),
            required_fields=["name", "value"],
        )
    )
    registry.register_class(
        OntologyClass(
            name="Finding",
            description="A specific observation within a pillar",
            required_fields=["rule", "severity"],
            optional_fields=["message", "path", "action", "verify"],
        )
    )

    registry.register_relationship(
        OntologyRelationship(
            name="has_score",
            source="Repository",
            target="Score",
            cardinality="one-to-one",
        )
    )
    registry.register_relationship(
        OntologyRelationship(
            name="measured_by",
            source="Score",
            target="Pillar",
            cardinality="one-to-many",
        )
    )
    registry.register_relationship(
        OntologyRelationship(
            name="contains",
            source="Pillar",
            target="Finding",
            cardinality="one-to-many",
        )
    )

    registry.register_taxonomy(
        Taxonomy(
            name="agent_readiness_pillars",
            parent=None,
            children=["cognitive_load", "feedback", "flow", "safety", "ontology"],
        )
    )
    for pillar in ("cognitive_load", "feedback", "flow", "safety", "ontology"):
        registry.register_taxonomy(
            Taxonomy(name=pillar, parent="agent_readiness_pillars")
        )

    registry.register_constraint(
        Constraint(
            name="repo_slug_format",
            applies_to="Repository",
            description="Slug must be in 'owner/name' format",
            validate=lambda e: isinstance(e.get("slug"), str)
            and "/" in e.get("slug", ""),
        )
    )
    registry.register_constraint(
        Constraint(
            name="score_range",
            applies_to="Score",
            description="Overall score must be between 0 and 100",
            validate=lambda e: isinstance(e.get("overall"), (int, float))
            and 0 <= e["overall"] <= 100,
        )
    )
    registry.register_constraint(
        Constraint(
            name="severity_enum",
            applies_to="Finding",
            description="Severity must be info, warn, or error",
            validate=lambda e: e.get("severity") in {"info", "warn", "error"},
        )
    )

    registry.register_rule(
        Rule(
            name="flag_low_score",
            condition="Score.overall < 50",
            action="Escalate for manual review",
        )
    )
    registry.register_rule(
        Rule(
            name="infer_pillar_names",
            condition="Pillar.name not set",
            action="Default pillar names from taxonomy",
        )
    )

    return registry
