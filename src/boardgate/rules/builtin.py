"""Built-in v1 rule bindings."""

from boardgate.rules.file_rules import DrillFilePresentRule, RequiredLayersPresentRule
from boardgate.rules.registry import Rule, RuleRegistry


def builtin_rules() -> tuple[Rule, ...]:
    """Return implemented rules; completed incrementally during v0.1."""
    return (RequiredLayersPresentRule(), DrillFilePresentRule())


def build_builtin_registry(*, require_complete: bool = True) -> RuleRegistry:
    """Validate and order the built-in rule set."""
    return RuleRegistry.build(builtin_rules(), require_complete=require_complete)
