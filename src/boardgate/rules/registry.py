"""Validated deterministic rule registry and dependency ordering."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from boardgate.config.models import RuleId
from boardgate.rules.models import RuleEvaluation

if TYPE_CHECKING:
    from boardgate.rules.engine import RuleContext


class Rule(Protocol):
    """One atomic deterministic rule implementation."""

    @property
    def rule_id(self) -> RuleId:
        """Stable configured rule identifier."""

    @property
    def version(self) -> str:
        """Rule implementation version."""

    @property
    def dependencies(self) -> tuple[RuleId, ...]:
        """Upstream rule identifiers required before evaluation."""

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Return one complete evaluation or raise before publication."""


class RuleRegistryError(ValueError):
    """Invalid rule registration or dependency graph."""


@dataclass(frozen=True, slots=True)
class RuleRegistry:
    """Unique rule bindings in deterministic topological order."""

    ordered_rules: tuple[Rule, ...]

    @classmethod
    def build(
        cls,
        rules: Iterable[Rule],
        *,
        require_complete: bool = True,
    ) -> RuleRegistry:
        """Validate IDs, v1 versions, dependencies, completeness, and cycles."""
        registered = tuple(rules)
        by_id: dict[RuleId, Rule] = {}
        for rule in registered:
            if rule.rule_id in by_id:
                raise RuleRegistryError(f"duplicate rule binding: {rule.rule_id.value}")
            if rule.version != "1.0":
                raise RuleRegistryError(
                    f"unsupported rule version for {rule.rule_id.value}: {rule.version}"
                )
            by_id[rule.rule_id] = rule
        if require_complete:
            missing = sorted(set(RuleId) - by_id.keys(), key=str)
            extra = sorted(by_id.keys() - set(RuleId), key=str)
            if missing or extra:
                labels = ", ".join(rule_id.value for rule_id in (*missing, *extra))
                raise RuleRegistryError(f"incomplete rule registry: {labels}")
        for rule in registered:
            unknown = sorted(set(rule.dependencies) - by_id.keys(), key=str)
            if unknown:
                labels = ", ".join(item.value for item in unknown)
                raise RuleRegistryError(
                    f"{rule.rule_id.value} has unknown dependencies: {labels}"
                )
            if rule.rule_id in rule.dependencies:
                raise RuleRegistryError(f"{rule.rule_id.value} cannot depend on itself")

        remaining = set(by_id)
        ordered: list[Rule] = []
        completed: set[RuleId] = set()
        while remaining:
            ready = sorted(
                (
                    rule_id
                    for rule_id in remaining
                    if set(by_id[rule_id].dependencies) <= completed
                ),
                key=str,
            )
            if not ready:
                labels = ", ".join(item.value for item in sorted(remaining, key=str))
                raise RuleRegistryError(f"rule dependency cycle: {labels}")
            for rule_id in ready:
                ordered.append(by_id[rule_id])
                completed.add(rule_id)
                remaining.remove(rule_id)
        return cls(ordered_rules=tuple(ordered))
