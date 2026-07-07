"""DEM (digital elevation model) helpers for elevation-gain computation."""

from __future__ import annotations

import contextlib
import math
import shutil
import time
from collections.abc import Sequence
from pathlib import Path

import rasterio
import requests
from rasterio.merge import merge as _merge

from telttur.config import BBox
from telttur.geo import CRS_UTM33, bbox_to_utm33

_DTM50_WCS = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm-nhm-25833"
_DTM50_COVERAGE = "nhm_dtm_topo_25833"
_CT_TIFF = "tiff"
_CT_OCTET = "octet-stream"
# Service pixel limit: 3840 cols × 2160 rows. At 50 m resolution that caps each
# tile at ~180 km wide and ~100 km tall.
_MAX_TILE_W_M = 180_000  # 3600 pixels at 50 m — stays within 3840 col limit
_MAX_TILE_H_M = 100_000  # 2000 pixels at 50 m — stays within 2160 row limit
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_TILE_ATTEMPTS = 4  # 1 initial + 3 retries
# DEM coverage in UTM33 from WCS DescribeCoverage — tiles entirely outside are skipped.
_DEM_MIN_E, _DEM_MIN_N, _DEM_MAX_E, _DEM_MAX_N = -100_274, 6_399_724, 1_150_255, 8_000_275


def _download_dem_tile(  # noqa: PLR0913
    tile_path: Path, minx: float, miny: float, maxx: float, maxy: float, timeout_s: float
) -> None:
    """Download one DTM50 WCS tile and save to tile_path. Raises RuntimeError on failure."""
    params = {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": _DTM50_COVERAGE,
        "CRS": CRS_UTM33,
        "RESPONSECRS": CRS_UTM33,
        "BBOX": f"{minx:.0f},{miny:.0f},{maxx:.0f},{maxy:.0f}",
        "RESX": "50",
        "RESY": "50",
        "FORMAT": "GeoTIFF",
    }
    resp = None
    for attempt in range(1, _MAX_TILE_ATTEMPTS + 1):
        try:
            resp = requests.get(_DTM50_WCS, params=params, timeout=timeout_s)
            resp.raise_for_status()
            break
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if attempt < _MAX_TILE_ATTEMPTS and status in _RETRY_STATUSES:
                wait = 15 * (2 ** (attempt - 1))  # 15 s, 30 s, 60 s
                print(
                    f"      HTTP {status}, retrying in {wait}s "
                    f"(attempt {attempt}/{_MAX_TILE_ATTEMPTS}) ..."
                )
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to download DTM50: {exc}") from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt < _MAX_TILE_ATTEMPTS:
                wait = 15 * (2 ** (attempt - 1))  # 15 s, 30 s, 60 s
                print(
                    f"      {type(exc).__name__}, retrying in {wait}s "
                    f"(attempt {attempt}/{_MAX_TILE_ATTEMPTS}) ..."
                )
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to download DTM50: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to download DTM50: {exc}") from exc

    assert resp is not None
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

    For large bboxes the download is tiled to respect the WCS service pixel
    limits (_MAX_TILE_W_M × _MAX_TILE_H_M) and then merged.
    """
    cache_name = f"dem50_{bbox.south:.1f}_{bbox.west:.1f}_{bbox.north:.1f}_{bbox.east:.1f}.tif"
    cache_path = data_dir / cache_name
    if cache_path.exists():
        print(f"  Using cached DEM: {cache_path.name}")
        return cache_path

    data_dir.mkdir(parents=True, exist_ok=True)

    bounds = bbox_to_utm33(bbox)  # (minx, miny, maxx, maxy)
    pad = 500  # metres — cover lake/road points near the edge
    minx, miny, maxx, maxy = bounds[0] - pad, bounds[1] - pad, bounds[2] + pad, bounds[3] + pad

    width = maxx - minx
    height = maxy - miny
    bbox_label = f"{bbox.south:.1f}°N–{bbox.north:.1f}°N {bbox.west:.1f}°E–{bbox.east:.1f}°E"

    if width <= _MAX_TILE_W_M and height <= _MAX_TILE_H_M:
        print(f"  Downloading DTM50 for bbox {bbox_label} ...")
        _download_dem_tile(cache_path, minx, miny, maxx, maxy, timeout_s)
    else:
        n_cols = math.ceil(width / _MAX_TILE_W_M)
        n_rows = math.ceil(height / _MAX_TILE_H_M)
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
                # Skip tiles entirely outside the DEM coverage extent.
                if tx1 <= _DEM_MIN_E or tx0 >= _DEM_MAX_E:
                    continue
                if ty1 <= _DEM_MIN_N or ty0 >= _DEM_MAX_N:
                    continue
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
