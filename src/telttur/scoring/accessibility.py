"""Accessibility scoring dimension.

Scores each lake by distance to the nearest drivable road.
"""

from __future__ import annotations

import geopandas as gpd

from telttur.config import AccessibilityConfig
from telttur.scoring.common import (
    CRS_UTM33,
    LEVEL_NAMES,
    PopupField,
    TentabilityLevel,
)

SCORE_COLUMN = "accessibility_score"

POPUP_FIELDS: list[PopupField] = [
    ("accessibility_level", "Accessibility"),
    ("road_distance_m", "Distance to road (m)"),
]

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
      accessibility_score  — TentabilityLevel integer (1 = Terrible … 5 = Excellent)
      accessibility_level  — human-readable level name
    """
    lakes = lakes.copy()

    excluded = set(excluded_road_types) if excluded_road_types is not None else _NON_MOTORIZED
    drivable = (
        road_lines[~road_lines["category"].isin(excluded)]
        if "category" in road_lines.columns
        else road_lines
    )

    if drivable.empty:
        lakes["road_distance_m"] = float("inf")
        lakes[SCORE_COLUMN] = int(TentabilityLevel.TERRIBLE)
        lakes["accessibility_level"] = LEVEL_NAMES[TentabilityLevel.TERRIBLE]
        return lakes

    lakes_utm = lakes.to_crs(CRS_UTM33)
    roads_utm = drivable[["geometry"]].to_crs(CRS_UTM33)

    # sjoin_nearest computes minimum Euclidean distance (metres in UTM33).
    # Duplicate rows arise when multiple roads tie for nearest — take the min.
    joined = gpd.sjoin_nearest(
        lakes_utm[["geometry"]],
        roads_utm,
        how="left",
        distance_col="road_distance_m",
    )
    distances = joined.groupby(joined.index)["road_distance_m"].min()
    lakes["road_distance_m"] = (
        lakes.index.map(distances).fillna(float("inf")).round(1)
    )

    thresholds = config.thresholds

    def _score(d: float) -> int:
        if d <= thresholds.excellent:
            return int(TentabilityLevel.EXCELLENT)
        elif d <= thresholds.good:
            return int(TentabilityLevel.GOOD)
        elif d <= thresholds.fair:
            return int(TentabilityLevel.FAIR)
        elif d <= thresholds.poor:
            return int(TentabilityLevel.POOR)
        return int(TentabilityLevel.TERRIBLE)

    lakes[SCORE_COLUMN] = lakes["road_distance_m"].apply(_score)
    lakes["accessibility_level"] = lakes[SCORE_COLUMN].map(LEVEL_NAMES)
    return lakes
