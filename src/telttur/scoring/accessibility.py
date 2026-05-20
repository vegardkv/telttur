"""Accessibility scoring dimension.

Scores each lake by distance to the nearest drivable road.
"""

from __future__ import annotations

import geopandas as gpd

from telttur.config import AccessibilityConfig
from telttur.lakes import LakeCols
from telttur.scoring.common import (
    CRS_UTM33,
)

# Non-motorised road categories — excluded from accessibility scoring because
# they cannot be reached by car.
_NON_MOTORIZED: set[str] = {"gangOgSykkelveg", "sti"}


def score_accessibility(
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    config: AccessibilityConfig,
    excluded_road_types: list[str] | None = None,
) -> gpd.GeoDataFrame:
    """Score each lake by distance to the nearest drivable road.

    Road types listed in *excluded_road_types* are excluded because they
    cannot be reached by car.  Defaults to the module-level ``_NON_MOTORIZED``
    set when not provided.

    Added columns:
      road_distance_m      — metres to nearest drivable road (rounded to 1 dp)
    """
    lakes = lakes.copy()

    excluded = set(excluded_road_types) if excluded_road_types is not None else _NON_MOTORIZED
    drivable = (
        road_lines[~road_lines["category"].isin(excluded)]
        if "category" in road_lines.columns
        else road_lines
    )

    if drivable.empty:
        lakes[LakeCols.ROAD_DISTANCE_M] = float("inf")
        return lakes

    lakes_utm = lakes.to_crs(CRS_UTM33)
    roads_utm = drivable[["geometry"]].to_crs(CRS_UTM33)

    # sjoin_nearest computes minimum Euclidean distance (metres in UTM33).
    # Duplicate rows arise when multiple roads tie for nearest — take the min.
    joined = gpd.sjoin_nearest(
        lakes_utm[["geometry"]],
        roads_utm,
        how="left",
        distance_col=LakeCols.ROAD_DISTANCE_M,
    )
    distances = joined.groupby(joined.index)[LakeCols.ROAD_DISTANCE_M].min()
    lakes[LakeCols.ROAD_DISTANCE_M] = lakes.index.map(distances).fillna(float("inf")).round(1)

    return lakes
