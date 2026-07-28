"""Built-in v1 rule bindings."""

from boardgate.rules.assembly_rules import BOMPlacementReferenceMatchRule
from boardgate.rules.drill_rules import (
    MinimumAnnularRingRule,
    MinimumDrillDiameterRule,
)
from boardgate.rules.file_rules import (
    BoardOutlineClosedRule,
    BoardOutlinePresentRule,
    DrillFilePresentRule,
    MultipleOutlineRegionsRule,
    RequiredLayersPresentRule,
)
from boardgate.rules.geometry_rules import (
    GerberDrillCoordinateAlignmentRule,
    MinimumCopperSpacingRule,
    MinimumCopperToEdgeRule,
    MinimumTraceWidthRule,
)
from boardgate.rules.registry import Rule, RuleRegistry
from boardgate.rules.surface_rules import (
    MinimumSolderMaskDamRule,
    SilkscreenOverExposedPadRule,
)


def builtin_rules() -> tuple[Rule, ...]:
    """Return implemented rules; completed incrementally during v0.1."""
    return (
        RequiredLayersPresentRule(),
        DrillFilePresentRule(),
        BoardOutlinePresentRule(),
        BoardOutlineClosedRule(),
        MultipleOutlineRegionsRule(),
        GerberDrillCoordinateAlignmentRule(),
        MinimumTraceWidthRule(),
        MinimumCopperSpacingRule(),
        MinimumCopperToEdgeRule(),
        MinimumDrillDiameterRule(),
        MinimumAnnularRingRule(),
        SilkscreenOverExposedPadRule(),
        MinimumSolderMaskDamRule(),
        BOMPlacementReferenceMatchRule(),
    )


def build_builtin_registry(*, require_complete: bool = True) -> RuleRegistry:
    """Validate and order the built-in rule set."""
    return RuleRegistry.build(builtin_rules(), require_complete=require_complete)
