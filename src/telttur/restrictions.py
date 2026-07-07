"""Restriction flags for lakes (bitmask column: restrictions_mask).

Bit definitions
---------------
  bit 0  drikkevann  — drinking-water source (Mattilsynet)

Data source
-----------
  Provider : Mattilsynet
  Layer    : Mattilsynet_Innsjo_Drikkevann
  WMS      : https://kart.mattilsynet.no/wmscache/service
  Geonorge : 50f62bbe-b216-4e38-bd75-1a54744c1a53
  License  : Åpne data — ingen begrensninger på bruk

The layer is published WMS-only (no WFS or downloadable vector). We therefore
render it once as a tiled transparent raster (GetMap → PNG) covering the study
area, convert each tile to a binary GeoTIFF and merge them into a cached
coverage raster, then sample each lake's representative point. A pixel is a
drinking-water source iff its palette entry is non-transparent. This costs
O(tiles) requests regardless of lake count (vs one GetFeatureInfo per lake) and
re-runs are free thanks to the cached GeoTIFF.
"""

from __future__ import annotations

import contextlib
import math
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.merge import merge as _merge
from rasterio.transform import from_bounds

from telttur.geo import CRS_UTM33
from telttur.lakes import LakeCols

# Bit definitions exported to the frontend config block.
RESTRICTIONS: list[dict[str, object]] = [
    {"bit": 0, "key": "drikkevann"},
]

DRINKING_WATER_BIT = 0

_WMS_URL = "https://kart.mattilsynet.no/wmscache/service"
_DW_LAYER = "Mattilsynet_Innsjo_Drikkevann"
# Ground resolution of the rendered coverage (matches N50/DTM50 detail).
_RES_M = 50.0
# WMS GetMap tile cap per dimension (150 km at 50 m). The Mattilsynet cache
# server returns HTTP 500 for renders larger than ~3000 px per side.
_MAX_TILE_PX = 3000
# Pad the render extent so every lake point falls safely inside the coverage.
_PAD_M = 500.0
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_TILE_ATTEMPTS = 4  # 1 initial + 3 retries
_CT_PNG = "image/png"


def _painted_mask(band: np.ndarray, colormap: dict[int, tuple[int, int, int, int]]) -> np.ndarray:
    """Map palette indices to a 0/1 uint8 mask (1 where the palette is non-transparent)."""
    lut = np.zeros(256, dtype=np.uint8)  # palette indices of an 8-bit band are 0..255
    for idx, rgba in colormap.items():
        if rgba[3] > 0:
            lut[idx] = 1
    return lut[band]


def _download_dw_tile(  # noqa: PLR0913
    tile_path: Path,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    width_px: int,
    height_px: int,
    timeout_s: float,
) -> None:
    """Render one WMS tile and save it as a binary (0/1) GeoTIFF. Raises on failure."""
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": _DW_LAYER,
        "STYLES": "",
        "CRS": CRS_UTM33,
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": str(width_px),
        "HEIGHT": str(height_px),
        "FORMAT": _CT_PNG,
        "TRANSPARENT": "TRUE",
    }
    resp = None
    for attempt in range(1, _MAX_TILE_ATTEMPTS + 1):
        try:
            resp = requests.get(_WMS_URL, params=params, timeout=timeout_s)
            resp.raise_for_status()
            break
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if attempt < _MAX_TILE_ATTEMPTS and status in _RETRY_STATUSES:
                wait = 5 * (2 ** (attempt - 1))  # 5 s, 10 s, 20 s
                print(
                    f"      HTTP {status}, retrying in {wait}s "
                    f"(attempt {attempt}/{_MAX_TILE_ATTEMPTS}) ..."
                )
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to fetch Mattilsynet WMS tile: {exc}") from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt < _MAX_TILE_ATTEMPTS:
                wait = 5 * (2 ** (attempt - 1))  # 5 s, 10 s, 20 s
                print(
                    f"      {type(exc).__name__}, retrying in {wait}s "
                    f"(attempt {attempt}/{_MAX_TILE_ATTEMPTS}) ..."
                )
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to fetch Mattilsynet WMS tile: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch Mattilsynet WMS tile: {exc}") from exc

    assert resp is not None
    ct = resp.headers.get("Content-Type", "").lower()
    if _CT_PNG not in ct:
        preview = resp.text[:300].replace("\n", " ")
        raise RuntimeError(f"WMS returned unexpected Content-Type {ct!r}. Response: {preview}")

    with MemoryFile(resp.content) as mem, mem.open() as src:
        band = src.read(1)
        try:
            colormap = src.colormap(1)
        except ValueError as exc:  # paletted PNG expected from this layer
            raise RuntimeError("WMS PNG had no colour palette; cannot detect features") from exc

    painted = _painted_mask(band, colormap)
    transform = from_bounds(minx, miny, maxx, maxy, width_px, height_px)
    with rasterio.open(
        tile_path,
        "w",
        driver="GTiff",
        height=height_px,
        width=width_px,
        count=1,
        dtype="uint8",
        crs=CRS_UTM33,
        transform=transform,
    ) as dst:
        dst.write(painted, 1)


def _ensure_dw_coverage(  # noqa: PLR0913
    data_dir: Path,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    timeout_s: float,
) -> Path:
    """Return a cached binary GeoTIFF of drinking-water coverage, rendering if absent."""
    cache_name = f"dw_drikkevann_{minx:.0f}_{miny:.0f}_{maxx:.0f}_{maxy:.0f}.tif"
    cache_path = data_dir / cache_name
    if cache_path.exists():
        print(f"  Using cached drinking-water coverage: {cache_path.name}")
        return cache_path

    data_dir.mkdir(parents=True, exist_ok=True)

    # Snap the extent to the pixel grid, keeping (minx, maxy) as the top-left origin.
    total_w = max(1, math.ceil((maxx - minx) / _RES_M))
    total_h = max(1, math.ceil((maxy - miny) / _RES_M))
    maxx = minx + total_w * _RES_M
    miny = maxy - total_h * _RES_M

    n_col_tiles = math.ceil(total_w / _MAX_TILE_PX)
    n_row_tiles = math.ceil(total_h / _MAX_TILE_PX)
    print(
        f"  Rendering Mattilsynet drinking-water layer "
        f"({total_w}×{total_h} px, {n_col_tiles}×{n_row_tiles} tile(s)) ..."
    )

    tile_dir = data_dir / f"_dwtiles_{cache_name[14:-4]}"
    tile_dir.mkdir(exist_ok=True)
    tile_paths: list[Path] = []
    for r in range(n_row_tiles):
        for c in range(n_col_tiles):
            px_x0, px_x1 = c * _MAX_TILE_PX, min((c + 1) * _MAX_TILE_PX, total_w)
            px_y0, px_y1 = r * _MAX_TILE_PX, min((r + 1) * _MAX_TILE_PX, total_h)
            w, h = px_x1 - px_x0, px_y1 - px_y0
            tx0 = minx + px_x0 * _RES_M
            tx1 = minx + px_x1 * _RES_M
            tymax = maxy - px_y0 * _RES_M  # row 0 is the top (highest northing)
            tymin = maxy - px_y1 * _RES_M
            tile_path = tile_dir / f"tile_{c}_{r}.tif"
            if not tile_path.exists():
                _download_dw_tile(tile_path, tx0, tymin, tx1, tymax, w, h, timeout_s)
            tile_paths.append(tile_path)

    if len(tile_paths) == 1:
        tile_paths[0].replace(cache_path)
    else:
        with contextlib.ExitStack() as stack:
            datasets = [stack.enter_context(rasterio.open(p)) for p in tile_paths]
            _merge(datasets, dst_path=str(cache_path), dst_kwds={"driver": "GTiff"})
    with contextlib.suppress(OSError):
        for p in tile_paths:
            p.unlink(missing_ok=True)
        tile_dir.rmdir()
    return cache_path


def tag_drinking_water(
    lakes: gpd.GeoDataFrame,
    data_dir: Path,
    timeout_s: float = 120.0,
) -> gpd.GeoDataFrame:
    """Add a restrictions_mask column, setting bit 0 for drinking-water source lakes.

    Renders the Mattilsynet drinking-water WMS layer over the lakes' extent into
    a cached GeoTIFF (data_dir/dw_drikkevann_*.tif), then samples each lake's
    representative point.
    """
    lakes = lakes.copy()
    # Category 3: no lakes means nothing to tag (defensive guard).
    if lakes.empty:
        lakes[LakeCols.RESTRICTIONS_MASK] = np.array([], dtype=int)
        return lakes

    pts = lakes.to_crs(CRS_UTM33).geometry.representative_point()
    valid = pts.notna().to_numpy() & ~pts.is_empty.to_numpy()
    xs = pts.x.to_numpy()
    ys = pts.y.to_numpy()

    vx, vy = xs[valid], ys[valid]
    minx, maxx = vx.min() - _PAD_M, vx.max() + _PAD_M
    miny, maxy = vy.min() - _PAD_M, vy.max() + _PAD_M

    coverage = _ensure_dw_coverage(data_dir, minx, miny, maxx, maxy, timeout_s)

    masks = np.zeros(len(lakes), dtype=int)
    with rasterio.open(coverage) as src:
        # Sample valid points only; out-of-extent is impossible (extent derives from points).
        coords = list(zip(vx, vy, strict=True))
        hits = np.array([vals[0] > 0 for vals in src.sample(coords)], dtype=bool)
    masks[valid] = np.where(hits, 1 << DRINKING_WATER_BIT, 0)

    lakes[LakeCols.RESTRICTIONS_MASK] = masks
    print(f"  Drinking-water lakes flagged: {int((masks != 0).sum())}/{len(lakes)}")
    return lakes
