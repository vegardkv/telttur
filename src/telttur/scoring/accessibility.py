"""Accessibility scoring dimension.

Scores each lake by distance to the nearest *access origin* and by the vertical
gain between that origin and the lake. Two origin types are computed so the
frontend can let the user choose how they arrive:

  * the nearest drivable road        → road_distance_m / elevation_gain_m
  * the nearest public-transport stop → transit_distance_m / transit_elevation_gain_m
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


def _score_origin(  # noqa: PLR0913
    lakes: gpd.GeoDataFrame,
    lakes_utm: gpd.GeoDataFrame,
    lake_pts_utm: gpd.GeoSeries,
    lake_elevs: list[float],
    origins: gpd.GeoDataFrame,
    dem_path: Path,
    *,
    dist_col: str,
    gain_col: str,
) -> None:
    """Add nearest-origin distance and |climb| columns to ``lakes`` in place.

    ``origins`` geometries may be lines (roads) or points (stops); the nearest
    point on the matched origin is sampled against the DEM either way.
    """
    # Category 3: no access origins in the region → inf distance is the correct result.
    if origins.empty:
        lakes[dist_col] = float("inf")
        lakes[gain_col] = 0.0
        return

    origins_utm = origins[["geometry"]].to_crs(CRS_UTM33)

    # sjoin_nearest computes minimum Euclidean distance (metres in UTM33).
    # Duplicate rows arise when multiple origins tie for nearest — take the min.
    joined = gpd.sjoin_nearest(
        lakes_utm[["geometry"]],
        origins_utm,
        how="left",
        distance_col=dist_col,
    )
    distances = joined.groupby(joined.index)[dist_col].min()
    lakes[dist_col] = lakes.index.map(distances).fillna(float("inf")).round(1)

    origin_idx_per_lake = joined.groupby(joined.index)["index_right"].first()
    origin_sample: list[tuple[float, float]] = []
    for lake_idx in lakes.index:
        lpt = lake_pts_utm.loc[lake_idx]
        origin_idx = origin_idx_per_lake.get(lake_idx)
        if origin_idx is not None and origin_idx in origins_utm.index:
            _, opt = nearest_points(lpt, origins_utm.geometry.loc[origin_idx])
            origin_sample.append((opt.x, opt.y))
        else:
            origin_sample.append((lpt.x, lpt.y))

    origin_elevs = sample_elevations(dem_path, origin_sample)
    lakes[gain_col] = [
        round(abs(le - oe), 1) for le, oe in zip(lake_elevs, origin_elevs, strict=True)
    ]


def score_accessibility(  # noqa: PLR0913
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    config: AccessibilityConfig,
    excluded_road_types: list[str] | None = None,
    *,
    dem_path: Path,
    stops: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Score each lake by distance and elevation gain to road and transit origins.

    Added columns:
      road_distance_m            — metres to nearest drivable road (1 dp)
      elevation_gain_m           — |lake elev − road elev| in metres (1 dp)
      transit_distance_m         — metres to nearest public-transport stop (1 dp)
      transit_elevation_gain_m   — |lake elev − stop elev| in metres (1 dp)

    ``transit_*`` columns are only added when ``stops`` is provided.
    """
    _CATEGORY_LABEL = "category"
    lakes = lakes.copy()

    lakes_utm = lakes.to_crs(CRS_UTM33)
    lake_pts_utm = lakes_utm.geometry.representative_point()
    lake_sample = [(pt.x, pt.y) for pt in lake_pts_utm]
    lake_elevs = sample_elevations(dem_path, lake_sample)

    excluded = set(excluded_road_types) if excluded_road_types is not None else _NON_MOTORIZED
    drivable = (
        road_lines[~road_lines["category"].isin(excluded)]
        if _CATEGORY_LABEL in road_lines.columns
        else road_lines
    )
    _score_origin(
        lakes,
        lakes_utm,
        lake_pts_utm,
        lake_elevs,
        drivable,
        dem_path,
        dist_col=LakeCols.ROAD_DISTANCE_M,
        gain_col=LakeCols.ELEVATION_GAIN_M,
    )

    if stops is not None:
        _score_origin(
            lakes,
            lakes_utm,
            lake_pts_utm,
            lake_elevs,
            stops,
            dem_path,
            dist_col=LakeCols.TRANSIT_DISTANCE_M,
            gain_col=LakeCols.TRANSIT_ELEVATION_GAIN_M,
        )

    return lakes
