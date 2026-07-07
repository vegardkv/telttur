"""Shared CRS constants and projection helpers.

N50 and most Norwegian national datasets use EUREF89 UTM zone 33 (EPSG:25833);
the Leaflet frontend uses WGS84 (EPSG:4326).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox

EPSG_CODE_UTM33 = 25833
CRS_UTM33 = f"EPSG:{EPSG_CODE_UTM33}"
CRS_WGS84 = "EPSG:4326"


def bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    """Convert a WGS84 bbox to UTM33 bounds (minx, miny, maxx, maxy)."""
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    b = bbox_gdf.to_crs(CRS_UTM33).total_bounds
    return (b[0], b[1], b[2], b[3])


def read_n50_layer(
    gdb_path: Path,
    layer: str,
    utm_bounds: tuple[float, float, float, float],
    geom_types: tuple[str, ...] | None = None,
) -> gpd.GeoDataFrame:
    """Read one N50 GDB layer pre-filtered to *utm_bounds*, normalised to UTM33.

    Optionally keeps only the given geometry types (e.g. ("Polygon", "MultiPolygon")).
    """
    gdf = gpd.read_file(str(gdb_path), layer=layer, bbox=utm_bounds)
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_UTM33)
    elif gdf.crs.to_epsg() != EPSG_CODE_UTM33:
        gdf = gdf.to_crs(CRS_UTM33)
    if geom_types is not None:
        gdf = gdf[gdf.geometry.geom_type.isin(geom_types)]
    return gdf


def find_objtype_column(gdf: gpd.GeoDataFrame) -> str | None:
    """Return the object-type column name, probing the spellings seen in N50 data."""
    for candidate in ("objtype", "OBJTYPE", "objType"):
        if candidate in gdf.columns:
            return candidate
    return None
