"""Shared types and utilities for lake tentability scoring."""

from __future__ import annotations

from enum import IntEnum

import geopandas as gpd


class TentabilityLevel(IntEnum):
    TERRIBLE = 1
    POOR = 2
    FAIR = 3
    GOOD = 4
    EXCELLENT = 5


LEVEL_NAMES: dict[int, str] = {
    TentabilityLevel.TERRIBLE: "Terrible",
    TentabilityLevel.POOR: "Poor",
    TentabilityLevel.FAIR: "Fair",
    TentabilityLevel.GOOD: "Good",
    TentabilityLevel.EXCELLENT: "Excellent",
}

# Diverging red→green palette (matching road category palette conventions)
LEVEL_COLORS: dict[int, str] = {
    TentabilityLevel.TERRIBLE: "#d73027",
    TentabilityLevel.POOR: "#fc8d59",
    TentabilityLevel.FAIR: "#fee08b",
    TentabilityLevel.GOOD: "#91cf60",
    TentabilityLevel.EXCELLENT: "#1a9850",
}


def _print_distribution(label: str, lakes: gpd.GeoDataFrame, col: str) -> None:
    print(f"  {label} distribution:")
    for level in TentabilityLevel:
        count = (lakes[col] == int(level)).sum()
        print(f"    {LEVEL_NAMES[int(level)]}: {count} lakes")
