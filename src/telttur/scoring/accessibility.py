"""Accessibility scoring dimension.

Scores each lake by distance to the nearest drivable road, and optionally by
the vertical gain between the nearest road point and the lake.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.ops import nearest_points

from telttur.config import AccessibilityConfig
from telttur.elevation import sample_elevations
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
    *,
    dem_path: Path | None = None,
) -> gpd.GeoDataFrame:
    """Score each lake by distance to the nearest drivable road.

    If *dem_path* is provided, also computes ``elevation_gain_m``: absolute
    vertical difference between the lake and its nearest road point (metres).

    Added columns:
      road_distance_m   — metres to nearest drivable road (rounded to 1 dp)
      elevation_gain_m  — |lake elev − road elev| in metres; only when dem_path given
    """
    _CATEGORY_LABEL = "category"
    lakes = lakes.copy()

    excluded = set(excluded_road_types) if excluded_road_types is not None else _NON_MOTORIZED
    drivable = (
        road_lines[~road_lines["category"].isin(excluded)]
        if _CATEGORY_LABEL in road_lines.columns
        else road_lines
    )

    if drivable.empty:
        lakes[LakeCols.ROAD_DISTANCE_M] = float("inf")
        if dem_path is not None:
            lakes[LakeCols.ELEVATION_GAIN_M] = 0.0
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

    if dem_path is not None:
        road_idx_per_lake = joined.groupby(joined.index)["index_right"].first()
        lake_pts_utm = lakes_utm.geometry.representative_point()
        lake_sample: list[tuple[float, float]] = []
        road_sample: list[tuple[float, float]] = []

        for lake_idx in lakes.index:
            lpt = lake_pts_utm.loc[lake_idx]
            lake_sample.append((lpt.x, lpt.y))
            road_idx = road_idx_per_lake.get(lake_idx)
            if road_idx is not None and road_idx in roads_utm.index:
                _, rpt = nearest_points(lpt, roads_utm.loc[road_idx, "geometry"])
                road_sample.append((rpt.x, rpt.y))
            else:
                road_sample.append((lpt.x, lpt.y))

        lake_elevs = sample_elevations(dem_path, lake_sample)
        road_elevs = sample_elevations(dem_path, road_sample)
        lakes[LakeCols.ELEVATION_GAIN_M] = [
            round(abs(le - re), 1) for le, re in zip(lake_elevs, road_elevs, strict=True)
        ]

    return lakes
