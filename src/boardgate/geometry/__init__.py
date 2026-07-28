"""Derived geometry helpers; no Shapely object crosses this package boundary."""

from boardgate.geometry.arcs import ArcApproximation, approximate_arc

__all__ = ["ArcApproximation", "approximate_arc"]
