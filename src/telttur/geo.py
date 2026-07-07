"""Shared CRS constants and projection helpers.

N50 and most Norwegian national datasets use EUREF89 UTM zone 33 (EPSG:25833);
the Leaflet frontend uses WGS84 (EPSG:4326).
"""

from __future__ import annotations

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
