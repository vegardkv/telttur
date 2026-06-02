"""DEM (digital elevation model) helpers for elevation-gain computation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from shapely.geometry import box

from telttur.config import BBox

_DTM50_WCS = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm50"
_DTM50_COVERAGE = "nhm_dtm_50"
_CRS_UTM33 = "EPSG:25833"
_CRS_WGS84 = "EPSG:4326"
_CT_TIFF = "tiff"
_CT_OCTET = "octet-stream"


def _ensure_dem(data_dir: Path, bbox: BBox, timeout_s: float = 120.0) -> Path:
    """Return path to cached DTM50 GeoTIFF for the given bbox, downloading if absent."""
    cache_name = f"dem50_{bbox.south:.1f}_{bbox.west:.1f}_{bbox.north:.1f}_{bbox.east:.1f}.tif"
    cache_path = data_dir / cache_name
    if cache_path.exists():
        print(f"  Using cached DEM: {cache_path}")
        return cache_path

    data_dir.mkdir(parents=True, exist_ok=True)

    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=_CRS_WGS84,
    )
    bounds = bbox_gdf.to_crs(_CRS_UTM33).total_bounds  # (minx, miny, maxx, maxy)
    pad = 500  # metres — cover lake/road points near the edge
    minx, miny, maxx, maxy = bounds[0] - pad, bounds[1] - pad, bounds[2] + pad, bounds[3] + pad

    params = {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": _DTM50_COVERAGE,
        "CRS": _CRS_UTM33,
        "RESPONSECRS": _CRS_UTM33,
        "BBOX": f"{minx:.0f},{miny:.0f},{maxx:.0f},{maxy:.0f}",
        "RESX": "50",
        "RESY": "50",
        "FORMAT": "image/tiff",
    }

    print(
        f"  Downloading DTM50 for bbox "
        f"{bbox.south:.1f}°N–{bbox.north:.1f}°N {bbox.west:.1f}°E–{bbox.east:.1f}°E ..."
    )
    try:
        resp = requests.get(_DTM50_WCS, params=params, timeout=timeout_s)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to download DTM50: {exc}") from exc

    ct = resp.headers.get("Content-Type", "").lower()
    if _CT_TIFF not in ct and _CT_OCTET not in ct:
        preview = resp.text[:300].replace("\n", " ")
        raise RuntimeError(f"WCS returned unexpected Content-Type {ct!r}. Response: {preview}")

    try:
        cache_path.write_bytes(resp.content)
    except OSError as exc:
        cache_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to save DTM50 raster: {exc}") from exc

    print(f"  Saved DEM: {cache_path} ({len(resp.content) / 1024:.0f} KB)")
    return cache_path


def sample_elevations(dem_path: Path, points_xy: Sequence[tuple[float, float]]) -> list[float]:
    """Sample elevation (metres) at each (x, y) UTM33 coordinate.

    Returns 0.0 for points outside the raster extent or on nodata cells.
    """
    with rasterio.open(dem_path) as src:
        nodata = src.nodata
        results = []
        for vals in src.sample(points_xy):
            v = float(vals[0])
            results.append(0.0 if nodata is not None and v == nodata else v)
    return results
