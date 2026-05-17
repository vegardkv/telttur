"""Shared types and utilities for lake tentability scoring."""

from __future__ import annotations

from enum import IntEnum

import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox
from telttur.lakes import LakeCols

CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"

# (column_name, display_label) — used by each dimension module to declare its popup fields
PopupField = tuple[str, str]


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


def _bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    b = bbox_gdf.to_crs(CRS_UTM33).total_bounds
    return (b[0], b[1], b[2], b[3])


def compute_tentability(
    lakes: gpd.GeoDataFrame,
    dimension_columns: list[str],
) -> gpd.GeoDataFrame:
    """Compute the composite tentability score as the *worst* of all dimensions.

    Added columns:
      tentability_score  — integer 1–5 (min of all dimension scores)
      tentability_level  — human-readable name (e.g. "Good")
      tentability_color  — hex colour for map display
    """
    lakes = lakes.copy()
    present = [c for c in dimension_columns if c in lakes.columns]
    lakes[LakeCols.TENTABILITY_SCORE] = (
        lakes[present].min(axis=1).astype(int) if present else int(TentabilityLevel.FAIR)
    )
    lakes[LakeCols.TENTABILITY_LEVEL] = lakes[LakeCols.TENTABILITY_SCORE].map(LEVEL_NAMES)
    lakes[LakeCols.TENTABILITY_COLOR] = lakes[LakeCols.TENTABILITY_SCORE].map(LEVEL_COLORS)
    return lakes


def _print_distribution(label: str, lakes: gpd.GeoDataFrame, col: str) -> None:
    print(f"  {label} distribution:")
    for level in TentabilityLevel:
        count = (lakes[col] == int(level)).sum()
        print(f"    {LEVEL_NAMES[int(level)]}: {count} lakes")
