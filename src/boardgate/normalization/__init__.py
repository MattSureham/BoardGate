"""Deterministic normalization from parser results into PCBProject IR."""

from boardgate.normalization.layers import normalize_gerber_layer
from boardgate.normalization.outline import (
    OutlineReconstruction,
    reconstruct_board_outline,
)

__all__ = [
    "OutlineReconstruction",
    "normalize_gerber_layer",
    "reconstruct_board_outline",
]
