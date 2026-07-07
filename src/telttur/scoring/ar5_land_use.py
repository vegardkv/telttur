"""AR5 land use proximity scoring dimension.

Scores each lake by its proximity to industrial and residential zones,
fetched from the NIBIO AR5 WFS or extracted from N50 arealdekke as a fallback.
"""

from __future__ import annotations

import io
from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd
import requests

from telttur.config import Ar5DataSource, Ar5LandUseConfig, BBox
from telttur.geo import (
    CRS_UTM33,
    EPSG_CODE_UTM33,
    bbox_to_utm33,
    find_objtype_column,
    read_n50_layer,
)
from telttur.lakes import LakeCols

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
    utm_bounds = bbox_to_utm33(bbox)
    minx, miny, maxx, maxy = utm_bounds

    params: dict[str, str] = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "Arealtype",
        "OUTPUTFORMAT": "application/json",
        "SRSNAME": CRS_UTM33,
        "BBOX": f"{minx:.1f},{miny:.1f},{maxx:.1f},{maxy:.1f},{CRS_UTM33}",
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

    # Category 3: a successful query with zero features means the bbox has no AR5 zones.
    if gdf.empty:
        return gpd.GeoDataFrame(columns=["geometry", "artype"], crs=CRS_UTM33)

    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_UTM33)
    elif gdf.crs.to_epsg() != EPSG_CODE_UTM33:
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
    gdf["artype"] = pd.to_numeric(gdf["artype"], errors="coerce").astype("Int64")
    return gdf[["geometry", "artype"]]


def _extract_n50_land_use_zones(
    gdb_paths: list[Path],
    bbox: BBox,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Extract industrial and residential polygons from N50 arealdekke layers.

    Used as a fallback when the AR5 WFS is unavailable.  Returns
    ``(industrial, residential)`` GeoDataFrames in UTM33.

    Filters to only industrial/residential polygons per GDB before accumulating
    to avoid loading the entire arealdekke dataset into memory.
    """
    utm_bounds = bbox_to_utm33(bbox)

    industrial_frames: list[gpd.GeoDataFrame] = []
    residential_frames: list[gpd.GeoDataFrame] = []
    found_area_layer = False

    for gdb_path in gdb_paths:
        all_layers = fiona.listlayers(str(gdb_path))
        area_layers = [
            ln
            for ln in all_layers
            if any(kw in ln.lower() for kw in ("arealdekke", "arealbruk", "markslag"))
            and "omrade" in ln.lower()
        ]
        found_area_layer = found_area_layer or bool(area_layers)
        for layer_name in area_layers:
            gdf = read_n50_layer(
                gdb_path, layer_name, utm_bounds, geom_types=("Polygon", "MultiPolygon")
            )
            type_col = find_objtype_column(gdf)
            if type_col is None:
                continue

            lower_types = gdf[type_col].str.lower().fillna("")
            industrial_frames.append(
                gdf[lower_types.str.contains("|".join(_N50_INDUSTRIAL_TYPES), regex=True)][
                    ["geometry"]
                ].copy()
            )
            residential_frames.append(
                gdf[lower_types.str.contains("|".join(_N50_RESIDENTIAL_TYPES), regex=True)][
                    ["geometry"]
                ].copy()
            )

    # Category 1: a missing arealdekke layer means an incomplete N50 download. Raise
    # rather than return empty frames, which would silently become inf distances.
    # (A zone-free region still finds the layer and returns empty — that case is fine.)
    if not found_area_layer:
        names = ", ".join(p.name for p in gdb_paths)
        raise RuntimeError(
            f"No N50 arealdekke layer found in {names}; cannot build the AR5 land-use "
            "fallback. The N50 download may be incomplete."
        )

    empty = gpd.GeoDataFrame(columns=["geometry"], crs=CRS_UTM33)

    def _concat(frames: list[gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
        non_empty = [f for f in frames if not f.empty]
        if not non_empty:
            return empty
        return gpd.GeoDataFrame(pd.concat(non_empty, ignore_index=True), crs=CRS_UTM33)

    return _concat(industrial_frames), _concat(residential_frames)


def _fetch_and_split_wfs(bbox: BBox, timeout_s: float) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Fetch AR5 polygons via WFS and split into (industrial, residential)."""
    ar5 = _fetch_ar5_wfs(bbox, timeout_s=timeout_s)
    industrial = ar5[ar5["artype"].isin(_AR5_INDUSTRIAL_ARTYPES)][["geometry"]].copy()
    residential = ar5[ar5["artype"].isin(_AR5_RESIDENTIAL_ARTYPES)][["geometry"]].copy()
    print(f"  AR5 WFS: {len(industrial)} industrial, {len(residential)} residential polygons")
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
        return _fetch_and_split_wfs(bbox, wfs_timeout_s)

    # Ar5DataSource.AUTO: try WFS, fall back to N50
    print("  Attempting AR5 WFS fetch from NIBIO...")
    try:
        return _fetch_and_split_wfs(bbox, wfs_timeout_s)
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

    Lakes far from both zone types receive EXCELLENT; lakes closer than the
    configured clearance are penalised using a graduated scale.

    This function only computes the raw distance columns below — the actual
    score conversion happens interactively in ``web/app.js``. For reference,
    the per-zone-type scoring (``buffer_m`` = desired clearance B) is:
      dist ≥ B            → EXCELLENT
      dist ≥ 5/6 * B      → GOOD
      dist ≥ 4/6 * B      → FAIR
      dist > 1/2 * B      → POOR
      dist ≤ 1/2 * B      → TERRIBLE

    The dimension score is the *minimum* (worst) of the industrial and residential
    sub-scores.

    Added columns:
      industrial_distance_m  — metres to nearest industrial zone (inf if none)
      residential_distance_m — metres to nearest residential zone (inf if none)
    """
    lakes = lakes.copy()
    lakes_utm = lakes.to_crs(CRS_UTM33)

    def _distances_to(polygons: gpd.GeoDataFrame) -> gpd.GeoSeries:
        polys_utm = (
            polygons
            if polygons.crs is not None and polygons.crs.to_epsg() == EPSG_CODE_UTM33
            else polygons.to_crs(CRS_UTM33)
        )
        joined = gpd.sjoin_nearest(
            lakes_utm[["geometry"]],
            polys_utm[["geometry"]],
            how="left",
            distance_col="_dist",
        )
        return joined.groupby(joined.index)["_dist"].min()

    # Category 3: no zones in the region → inf distance (the best score) is correct.
    if industrial_polygons.empty:
        lakes[LakeCols.INDUSTRIAL_DISTANCE_M] = float("inf")
    else:
        ind_dist = _distances_to(industrial_polygons)
        lakes[LakeCols.INDUSTRIAL_DISTANCE_M] = (
            lakes.index.map(ind_dist).fillna(float("inf")).round(1)
        )
    if residential_polygons.empty:
        lakes[LakeCols.RESIDENTIAL_DISTANCE_M] = float("inf")
    else:
        res_dist = _distances_to(residential_polygons)
        lakes[LakeCols.RESIDENTIAL_DISTANCE_M] = (
            lakes.index.map(res_dist).fillna(float("inf")).round(1)
        )

    return lakes
