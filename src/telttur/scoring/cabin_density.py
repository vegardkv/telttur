"""Cabin density scoring dimension.

Scores each lake by the density of residential/cabin buildings near its shore.
"""

from __future__ import annotations

import math
from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox, CabinDensityConfig
from telttur.geo import CRS_UTM33, bbox_to_utm33, read_n50_layer
from telttur.lakes import LakeCols

# Norwegian building type codes (bygningstype) that indicate habitation:
#   100–199: Residential buildings, including:
#     161–169: Cabins/fritidsboliger (dominant in mountain areas)
#     111–119: Single-family homes, 121–129: Two-family homes, etc.
_RESIDENTIAL_MIN = 100
_RESIDENTIAL_MAX = 199


def find_building_layers(gdb_path: Path) -> list[str]:
    """List layers in a .gdb that contain building point data."""
    all_layers = fiona.listlayers(str(gdb_path))
    return [
        layer
        for layer in all_layers
        if any(kw in layer.lower() for kw in ("bygning", "building"))
        and "posisjon" in layer.lower()
    ]


def extract_buildings(gdb_paths: list[Path], bbox: BBox) -> gpd.GeoDataFrame:
    """Extract residential/cabin building points from N50 FGDB files, clipped to bbox.

    Filters to objtype == 'Bygning' and bygningstype 100–199 (residential/cabins).
    This excludes masts, tanks, industrial buildings, barns, churches, etc.
    """
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        for layer_name in find_building_layers(gdb_path):
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = read_n50_layer(gdb_path, layer_name, utm_bounds)

            if "objtype" in gdf.columns:
                gdf = gdf[gdf["objtype"] == "Bygning"]
            if "bygningstype" in gdf.columns:
                gdf = gdf[gdf["bygningstype"].between(_RESIDENTIAL_MIN, _RESIDENTIAL_MAX)]

            frames.append(gdf)

    if not frames:
        # Category 1: N50 always ships a building-point layer, so finding none means the
        # download is incomplete/corrupt. (Empty rows is the genuinely-no-buildings case.)
        names = ", ".join(p.name for p in gdb_paths)
        raise RuntimeError(
            f"No building-point layer found in N50 data ({names}); the N50 download may "
            "be incomplete. Delete the cache and re-run."
        )

    buildings = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs=CRS_UTM33)
    return buildings.clip(box(*utm_bounds))


def extract_buildings_all(gdb_paths: list[Path], bbox: BBox) -> gpd.GeoDataFrame:
    """Extract ALL building points from N50 FGDB files (no type filter), clipped to bbox.

    Keeps the ``bygningstype`` column so callers can inspect which types are
    present and whether the residential filter (100–199) is correct.  Only
    rows with ``objtype == 'Bygning'`` are kept; non-building point features
    (masts, tanks, etc.) are excluded.

    Used for debugging only — not called in the normal pipeline.
    """
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        for layer_name in find_building_layers(gdb_path):
            print(f"  Reading {layer_name} from {gdb_path.name} (debug)...")
            gdf = read_n50_layer(gdb_path, layer_name, utm_bounds)

            if "objtype" in gdf.columns:
                gdf = gdf[gdf["objtype"] == "Bygning"]

            # Keep only geometry + type code — everything else is noise for debugging
            keep = ["geometry"]
            if "bygningstype" in gdf.columns:
                keep.append("bygningstype")
            frames.append(gdf[keep])

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry", "bygningstype"], crs=CRS_UTM33)

    buildings = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs=CRS_UTM33)
    return buildings.clip(box(*utm_bounds))


def score_cabin_density(
    lakes: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    config: CabinDensityConfig,
) -> gpd.GeoDataFrame:
    """Score each lake by cabin/building density near its shore.

    Density is defined as ``building_count / sqrt(area_m2)``, which normalises
    for lake size so that a large remote lake with a handful of cabins is not
    penalised as harshly as a small lake surrounded by the same number of
    buildings.  ``sqrt(area_m2)`` is used as a proxy for shoreline length.

    The ``area_m2`` column must already be present on *lakes* (added by
    ``process_lakes``).

    Added columns:
      building_count       — number of buildings within the buffer
      building_density     — building_count / sqrt(area_m2), rounded to 4 dp
    """
    lakes = lakes.copy()
    lakes_utm = lakes.to_crs(CRS_UTM33).copy()
    buildings_utm = buildings if str(buildings.crs) == CRS_UTM33 else buildings.to_crs(CRS_UTM33)

    # Buffer all lake polygons at once, then count buildings inside each buffer
    lakes_utm["_buf"] = lakes_utm.geometry.buffer(config.buffer_m)
    lake_buffers = lakes_utm[["_buf"]].set_geometry("_buf").rename_geometry("geometry")
    lake_buffers.index = lakes_utm.index

    joined = gpd.sjoin(lake_buffers, buildings_utm[["geometry"]], how="left", predicate="contains")
    building_count = joined.groupby(joined.index)["index_right"].count()
    lakes[LakeCols.BUILDING_COUNT] = lakes.index.map(building_count).fillna(0).astype(int)

    # Normalise by sqrt(area_m2) — use area_m2 when available, fall back to
    # computing area in UTM to avoid zero-division.
    if LakeCols.AREA_M2 in lakes.columns:
        area_m2 = lakes[LakeCols.AREA_M2]
    else:
        area_m2 = lakes.to_crs(CRS_UTM33).geometry.area

    sqrt_area = area_m2.apply(lambda a: math.sqrt(max(a, 1.0)))
    # Multiply by 10000 to get buildings per ha
    lakes[LakeCols.BUILDING_DENSITY] = (10_000 * lakes[LakeCols.BUILDING_COUNT] / sqrt_area).round(
        4
    )

    return lakes
