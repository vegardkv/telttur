"""AR5 land use proximity scoring dimension.

Scores each lake by its proximity to industrial and residential zones,
fetched from the NIBIO AR5 WFS or extracted from N50 arealdekke as a fallback.
"""

from __future__ import annotations

import io
from pathlib import Path

import fiona
import geopandas as gpd
import requests
from shapely.geometry import box

from telttur.config import Ar5DataSource, Ar5LandUseConfig, BBox
from telttur.lakes import LakeCols
from telttur.scoring.common import (
    CRS_UTM33,
    LEVEL_NAMES,
    PopupField,
    TentabilityLevel,
    _bbox_to_utm33,
)

SCORE_COLUMN = LakeCols.AR5_LAND_USE_SCORE

SCORE_FIELDS: list[PopupField] = [
    (LakeCols.AR5_LAND_USE_LEVEL, "AR5 land use"),
]
DETAIL_FIELDS: list[PopupField] = [
    (LakeCols.INDUSTRIAL_DISTANCE_M, "Distance to industrial zone (m)"),
    (LakeCols.RESIDENTIAL_DISTANCE_M, "Distance to residential zone (m)"),
]
POPUP_FIELDS: list[PopupField] = SCORE_FIELDS + DETAIL_FIELDS

# NIBIO AR5 WFS endpoint — same server as the WMS, supports SERVICE=WFS
_AR5_WFS_URL = "https://wms.nibio.no/cgi-bin/ar5"

# AR5 artype codes (integer field on ArealressursFlateLand layer)
#   21 = Industri og næringsbebyggelse (industrial / commercial)
#   11 = Tettbebyggelse (dense residential / urban)
#   12 = Spredt bebyggelse (sparse residential)
_AR5_INDUSTRIAL_ARTYPES: frozenset[int] = frozenset({21})
_AR5_RESIDENTIAL_ARTYPES: frozenset[int] = frozenset({11, 12})

# N50 arealdekke objtype substrings used when WFS is unavailable
_N50_INDUSTRIAL_TYPES: tuple[str, ...] = ("industri",)
_N50_RESIDENTIAL_TYPES: tuple[str, ...] = ("tettbebyggelse",)


def _fetch_ar5_wfs(bbox: BBox, timeout_s: float = 30.0) -> gpd.GeoDataFrame:
    """Fetch AR5 land-use polygons from NIBIO WFS within *bbox*.

    Returns a GeoDataFrame in UTM33 with at least an ``artype`` integer column.
    Raises ``RuntimeError`` on any connectivity or parsing failure.
    """
    utm_bounds = _bbox_to_utm33(bbox)
    minx, miny, maxx, maxy = utm_bounds

    params: dict[str, str] = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "Arealtype",
        "OUTPUTFORMAT": "application/json",
        "SRSNAME": "EPSG:25833",
        "BBOX": f"{minx:.1f},{miny:.1f},{maxx:.1f},{maxy:.1f},EPSG:25833",
        "COUNT": "50000",
    }

    try:
        resp = requests.get(_AR5_WFS_URL, params=params, timeout=timeout_s)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"AR5 WFS request failed: {exc}") from exc

    try:
        gdf = gpd.read_file(io.BytesIO(resp.content))
    except Exception as exc:
        raise RuntimeError(f"Failed to parse AR5 WFS response: {exc}") from exc

    if gdf.empty:
        return gpd.GeoDataFrame(columns=["geometry", "artype"], crs=CRS_UTM33)

    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_UTM33)
    elif gdf.crs.to_epsg() != 25833:
        gdf = gdf.to_crs(CRS_UTM33)

    # Normalise the artype column — field may be named 'artype' or 'arealtype'
    artype_col: str | None = None
    for col in gdf.columns:
        if col.lower() in ("artype", "arealtype"):
            artype_col = col
            break

    if artype_col is None:
        raise RuntimeError("AR5 WFS response is missing an artype/arealtype field")

    gdf = gdf.rename(columns={artype_col: "artype"})
    gdf["artype"] = gpd.pd.to_numeric(gdf["artype"], errors="coerce").astype("Int64")
    return gdf[["geometry", "artype"]]


def _extract_n50_land_use_zones(
    gdb_paths: list[Path],
    bbox: BBox,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Extract industrial and residential polygons from N50 arealdekke layers.

    Used as a fallback when the AR5 WFS is unavailable.  Returns
    ``(industrial, residential)`` GeoDataFrames in UTM33.
    """
    utm_bounds = _bbox_to_utm33(bbox)
    clip_box = box(*utm_bounds)

    frames: list[gpd.GeoDataFrame] = []
    for gdb_path in gdb_paths:
        all_layers = fiona.listlayers(str(gdb_path))
        area_layers = [
            ln
            for ln in all_layers
            if any(kw in ln.lower() for kw in ("arealdekke", "arealbruk", "markslag"))
            and "omrade" in ln.lower()
        ]
        for layer_name in area_layers:
            gdf = gpd.read_file(str(gdb_path), layer=layer_name, bbox=utm_bounds)
            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif gdf.crs.to_epsg() != 25833:
                gdf = gdf.to_crs(CRS_UTM33)
            gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
            frames.append(gdf)

    empty = gpd.GeoDataFrame(columns=["geometry"], crs=CRS_UTM33)
    if not frames:
        return empty, empty

    combined = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs=CRS_UTM33).clip(
        clip_box
    )

    type_col: str | None = None
    for candidate in ("objtype", "OBJTYPE", "objType"):
        if candidate in combined.columns:
            type_col = candidate
            break

    if type_col is None:
        return empty, empty

    lower_types = combined[type_col].str.lower().fillna("")
    industrial = combined[lower_types.str.contains("|".join(_N50_INDUSTRIAL_TYPES), regex=True)][
        ["geometry"]
    ].copy()
    residential = combined[lower_types.str.contains("|".join(_N50_RESIDENTIAL_TYPES), regex=True)][
        ["geometry"]
    ].copy()
    return industrial, residential


def fetch_ar5_land_use_polygons(
    gdb_paths: list[Path],
    bbox: BBox,
    config: Ar5LandUseConfig,
    wfs_timeout_s: float = 30.0,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Return ``(industrial, residential)`` polygon GeoDataFrames in UTM33.

    The data source is controlled by ``config.source``:
      - ``auto``: try the NIBIO AR5 WFS first; fall back to N50 on failure.
      - ``wfs``:  always use the NIBIO AR5 WFS (raises on failure).
      - ``n50``:  always use the local N50 arealdekke data.

    Both returned frames contain only a ``geometry`` column and may be empty.
    """
    if config.source == Ar5DataSource.N50:
        print("  Using N50 arealdekke for AR5 land use (source=n50)...")
        industrial, residential = _extract_n50_land_use_zones(gdb_paths, bbox)
        print(f"  N50: {len(industrial)} industrial, {len(residential)} residential polygons")
        return industrial, residential

    if config.source == Ar5DataSource.WFS:
        print("  Fetching AR5 land use from NIBIO WFS (source=wfs)...")
        ar5 = _fetch_ar5_wfs(bbox, timeout_s=wfs_timeout_s)
        industrial = ar5[ar5["artype"].isin(_AR5_INDUSTRIAL_ARTYPES)][["geometry"]].copy()
        residential = ar5[ar5["artype"].isin(_AR5_RESIDENTIAL_ARTYPES)][["geometry"]].copy()
        print(f"  AR5 WFS: {len(industrial)} industrial, {len(residential)} residential polygons")
        return industrial, residential

    # Ar5DataSource.AUTO: try WFS, fall back to N50
    print("  Attempting AR5 WFS fetch from NIBIO...")
    try:
        ar5 = _fetch_ar5_wfs(bbox, timeout_s=wfs_timeout_s)
        industrial = ar5[ar5["artype"].isin(_AR5_INDUSTRIAL_ARTYPES)][["geometry"]].copy()
        residential = ar5[ar5["artype"].isin(_AR5_RESIDENTIAL_ARTYPES)][["geometry"]].copy()
        print(f"  AR5 WFS: {len(industrial)} industrial, {len(residential)} residential polygons")
        return industrial, residential
    except RuntimeError as exc:
        print(f"  AR5 WFS unavailable ({exc}); falling back to N50 arealdekke")

    industrial, residential = _extract_n50_land_use_zones(gdb_paths, bbox)
    print(f"  N50 fallback: {len(industrial)} industrial, {len(residential)} residential polygons")
    return industrial, residential


def score_ar5_land_use(
    lakes: gpd.GeoDataFrame,
    industrial_polygons: gpd.GeoDataFrame,
    residential_polygons: gpd.GeoDataFrame,
    config: Ar5LandUseConfig,
) -> gpd.GeoDataFrame:
    """Score each lake by proximity to industrial and residential land-use zones.

    Lakes far from both zone types receive EXCELLENT; lakes within the configured
    distance thresholds are penalised using a graduated scale.

    Scoring per zone type (using ``buffer_m`` as the threshold distance):
      dist > buffer_m            → EXCELLENT
      dist > 0.75 * buffer_m    → GOOD
      dist > 0.50 * buffer_m    → FAIR
      dist > 0.25 * buffer_m    → POOR
      dist ≤ 0.25 * buffer_m    → TERRIBLE

    The dimension score is the *minimum* (worst) of the industrial and residential
    sub-scores.

    Added columns:
      industrial_distance_m  — metres to nearest industrial zone (inf if none)
      residential_distance_m — metres to nearest residential zone (inf if none)
      ar5_land_use_score     — TentabilityLevel integer (1 = Terrible … 5 = Excellent)
      ar5_land_use_level     — human-readable level name
    """
    lakes = lakes.copy()
    lakes_utm = lakes.to_crs(CRS_UTM33)

    def _distances_to(polygons: gpd.GeoDataFrame) -> gpd.GeoSeries:
        if polygons.empty:
            return gpd.pd.Series(float("inf"), index=lakes.index)
        polys_utm = (
            polygons
            if polygons.crs is not None and polygons.crs.to_epsg() == 25833
            else polygons.to_crs(CRS_UTM33)
        )
        joined = gpd.sjoin_nearest(
            lakes_utm[["geometry"]],
            polys_utm[["geometry"]],
            how="left",
            distance_col="_dist",
        )
        return joined.groupby(joined.index)["_dist"].min()

    ind_dist = _distances_to(industrial_polygons)
    res_dist = _distances_to(residential_polygons)

    lakes[LakeCols.INDUSTRIAL_DISTANCE_M] = lakes.index.map(ind_dist).fillna(float("inf")).round(1)
    lakes[LakeCols.RESIDENTIAL_DISTANCE_M] = lakes.index.map(res_dist).fillna(float("inf")).round(1)

    def _score_proximity(dist_m: float, buffer_m: float) -> int:
        if dist_m >= buffer_m:
            return int(TentabilityLevel.EXCELLENT)
        elif dist_m >= 0.75 * buffer_m:
            return int(TentabilityLevel.GOOD)
        elif dist_m >= 0.50 * buffer_m:
            return int(TentabilityLevel.FAIR)
        elif dist_m >= 0.25 * buffer_m:
            return int(TentabilityLevel.POOR)
        return int(TentabilityLevel.TERRIBLE)

    ind_scores = lakes[LakeCols.INDUSTRIAL_DISTANCE_M].apply(
        lambda d: _score_proximity(d, config.industrial_buffer_m)
    )
    res_scores = lakes[LakeCols.RESIDENTIAL_DISTANCE_M].apply(
        lambda d: _score_proximity(d, config.residential_buffer_m)
    )
    lakes[SCORE_COLUMN] = gpd.pd.concat([ind_scores, res_scores], axis=1).min(axis=1).astype(int)
    lakes[LakeCols.AR5_LAND_USE_LEVEL] = lakes[SCORE_COLUMN].map(LEVEL_NAMES)
    return lakes
