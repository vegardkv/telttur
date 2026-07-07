"""Public-transport stop extraction from Entur's national GTFS feed.

Provides the "distance to nearest public-transport stop" signal used by the
accessibility scoring dimension. Entur publishes Norway's aggregated national
GTFS as a single ~640 MB zip, but we need only its ``stops.txt`` member, so we
extract that one file via HTTP range requests instead of downloading the whole
archive.

Data source
-----------
- Provider: Entur (Norway's national public-transport registry)
- URL: https://storage.googleapis.com/marduk-production/outbound/gtfs/rb_norway-aggregated-gtfs.zip
- Format: GTFS zip; ``stops.txt`` is a CSV with stop_lat / stop_lon / location_type
- Licence: NLOD (Norsk lisens for offentlige data)
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from telttur.config import BBox
from telttur.geo import CRS_UTM33, CRS_WGS84

_GTFS_URL = (
    "https://storage.googleapis.com/marduk-production/outbound/gtfs/rb_norway-aggregated-gtfs.zip"
)
_STOPS_MEMBER = "stops.txt"
_STOPS_CACHE_NAME = "entur_stops.csv"

# GTFS location_type: "1" = parent station, blank/"0" = boarding stop. Keep only
# boarding stops so a station and its platforms are not double-counted.
_LOCATION_TYPE_STATION = "1"


class _HttpRangeReader(io.RawIOBase):
    """Seekable, read-only file backed by HTTP Range requests.

    Lets ``zipfile`` read a single member's directory entry, local header and
    data from a remote zip without downloading the whole archive — the central
    directory lives at the end of the file, which a sequential download would
    otherwise force us to fetch in full.
    """

    def __init__(self, url: str, timeout_s: float) -> None:
        self._url = url
        self._timeout_s = timeout_s
        self._pos = 0
        resp = requests.head(url, timeout=timeout_s)
        resp.raise_for_status()
        self._size = int(resp.headers["Content-Length"])

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._size + offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            end = self._size - 1
        else:
            end = min(self._pos + size - 1, self._size - 1)
        if self._pos > end:
            return b""
        headers = {"Range": f"bytes={self._pos}-{end}"}
        resp = requests.get(self._url, headers=headers, timeout=self._timeout_s)
        resp.raise_for_status()
        data = resp.content
        self._pos += len(data)
        return data


def _ensure_stops_cache(data_dir: Path, timeout_s: float) -> Path:
    """Return the cached Entur ``stops.txt``, extracting it via HTTP range if absent."""
    cache_path = data_dir / _STOPS_CACHE_NAME
    if cache_path.exists():
        print(f"  Using cached Entur stops: {cache_path.name}")
        return cache_path

    data_dir.mkdir(parents=True, exist_ok=True)
    print("  Extracting stops.txt from Entur national GTFS (HTTP range)...")
    try:
        reader = _HttpRangeReader(_GTFS_URL, timeout_s)
        with zipfile.ZipFile(reader) as zf, zf.open(_STOPS_MEMBER) as src:
            data = src.read()
    except (requests.RequestException, zipfile.BadZipFile, KeyError) as exc:
        raise RuntimeError(f"Failed to fetch Entur stops: {exc}") from exc

    try:
        cache_path.write_bytes(data)
    except OSError as exc:
        cache_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to cache Entur stops: {exc}") from exc

    return cache_path


def load_transit_stops(data_dir: Path, bbox: BBox, timeout_s: float = 120.0) -> gpd.GeoDataFrame:
    """Load Entur public-transport boarding stops, clipped to ``bbox``, in UTM33.

    Parent stations (GTFS location_type 1) are dropped so they do not
    double-count with their platforms. Returns a GeoDataFrame with a single
    Point geometry column.
    """
    cache_path = _ensure_stops_cache(data_dir, timeout_s)

    df = pd.read_csv(
        cache_path,
        usecols=["stop_lat", "stop_lon", "location_type"],
        dtype={"stop_lat": float, "stop_lon": float, "location_type": "string"},
    )
    df = df[df["location_type"].fillna("0") != _LOCATION_TYPE_STATION]
    df = df.dropna(subset=["stop_lat", "stop_lon"])

    # Clip to the run bbox in WGS84 before the (costly) reprojection.
    in_bbox = (
        (df["stop_lon"] >= bbox.west)
        & (df["stop_lon"] <= bbox.east)
        & (df["stop_lat"] >= bbox.south)
        & (df["stop_lat"] <= bbox.north)
    )
    df = df[in_bbox]

    stops = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(df["stop_lon"], df["stop_lat"]),
        crs=CRS_WGS84,
    )
    return stops.to_crs(CRS_UTM33)
