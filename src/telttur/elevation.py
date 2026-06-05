"""DEM (digital elevation model) helpers for elevation-gain computation."""

from __future__ import annotations

import contextlib
import math
import shutil
from collections.abc import Sequence
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from rasterio.merge import merge as _merge
from shapely.geometry import box

from telttur.config import BBox

_DTM50_WCS = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm50"
_DTM50_COVERAGE = "nhm_dtm_50"
_CRS_UTM33 = "EPSG:25833"
_CRS_WGS84 = "EPSG:4326"
_CT_TIFF = "tiff"
_CT_OCTET = "octet-stream"
# WCS service rejects requests wider/taller than this; large bboxes are tiled.
_MAX_TILE_EXTENT_M = 200_000  # 200 km per side → 4000×4000 pixels at 50 m


def _download_dem_tile(  # noqa: PLR0913
    tile_path: Path, minx: float, miny: float, maxx: float, maxy: float, timeout_s: float
) -> None:
    """Download one DTM50 WCS tile and save to tile_path. Raises RuntimeError on failure."""
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
        tile_path.write_bytes(resp.content)
    except OSError as exc:
        tile_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to save DTM50 raster: {exc}") from exc


def ensure_dem(data_dir: Path, bbox: BBox, timeout_s: float = 120.0) -> Path:
    """Return path to cached DTM50 GeoTIFF for the given bbox, downloading if absent.

    For large bboxes the download is split into tiles of at most
    _MAX_TILE_EXTENT_M per side and then merged into a single cached file.
    """
    cache_name = f"dem50_{bbox.south:.1f}_{bbox.west:.1f}_{bbox.north:.1f}_{bbox.east:.1f}.tif"
    cache_path = data_dir / cache_name
    if cache_path.exists():
        print(f"  Using cached DEM: {cache_path.name}")
        return cache_path

    data_dir.mkdir(parents=True, exist_ok=True)

    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=_CRS_WGS84,
    )
    bounds = bbox_gdf.to_crs(_CRS_UTM33).total_bounds  # (minx, miny, maxx, maxy)
    pad = 500  # metres — cover lake/road points near the edge
    minx, miny, maxx, maxy = bounds[0] - pad, bounds[1] - pad, bounds[2] + pad, bounds[3] + pad

    width = maxx - minx
    height = maxy - miny
    bbox_label = f"{bbox.south:.1f}°N–{bbox.north:.1f}°N {bbox.west:.1f}°E–{bbox.east:.1f}°E"

    if width <= _MAX_TILE_EXTENT_M and height <= _MAX_TILE_EXTENT_M:
        print(f"  Downloading DTM50 for bbox {bbox_label} ...")
        _download_dem_tile(cache_path, minx, miny, maxx, maxy, timeout_s)
    else:
        n_cols = math.ceil(width / _MAX_TILE_EXTENT_M)
        n_rows = math.ceil(height / _MAX_TILE_EXTENT_M)
        tile_w = width / n_cols
        tile_h = height / n_rows
        print(f"  Downloading DTM50 in {n_cols}×{n_rows} tiles for bbox {bbox_label} ...")
        tile_dir = data_dir / f"_tiles_{cache_name[5:-4]}"
        tile_dir.mkdir(exist_ok=True)
        tile_paths: list[Path] = []
        for row in range(n_rows):
            for col in range(n_cols):
                tx0 = minx + col * tile_w
                ty0 = miny + row * tile_h
                tx1 = tx0 + tile_w
                ty1 = ty0 + tile_h
                tile_path = tile_dir / f"tile_{col}_{row}.tif"
                if not tile_path.exists():
                    print(f"    tile ({col + 1}/{n_cols}, {row + 1}/{n_rows}) ...")
                    _download_dem_tile(tile_path, tx0, ty0, tx1, ty1, timeout_s)
                tile_paths.append(tile_path)

        print(f"  Merging {len(tile_paths)} DEM tiles ...")
        with contextlib.ExitStack() as stack:
            datasets = [stack.enter_context(rasterio.open(p)) for p in tile_paths]
            _merge(datasets, dst_path=str(cache_path), dst_kwds={"driver": "GTiff"})
        shutil.rmtree(tile_dir, ignore_errors=True)

    size_mb = cache_path.stat().st_size / 1024 / 1024
    print(f"  Saved DEM: {cache_path.name} ({size_mb:.0f} MB)")
    return cache_path


def sample_elevations(dem_path: Path, points_xy: Sequence[tuple[float, float]]) -> list[float]:
    """Sample elevation (metres) at each (x, y) UTM33 coordinate.

    Raises RuntimeError if any point lies outside the raster extent — the DEM
    is padded 500 m around the study area, so out-of-extent is a bug.
    Returns 0.0 for genuine nodata cells (e.g. sea).
    """
    with rasterio.open(dem_path) as src:
        left, bottom, right, top = src.bounds
        for x, y in points_xy:
            if not (left <= x <= right and bottom <= y <= top):
                raise RuntimeError(
                    f"Point ({x:.1f}, {y:.1f}) lies outside DEM extent "
                    f"({left:.0f}–{right:.0f} E, {bottom:.0f}–{top:.0f} N). "
                    "Re-download the DEM with a larger padding."
                )
        nodata = src.nodata
        results = []
        for vals in src.sample(points_xy):
            v = float(vals[0])
            results.append(0.0 if nodata is not None and v == nodata else v)
    return results
