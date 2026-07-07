"""Fishing suitability scoring dimension.

Scores each lake by the diversity and quality of fish species observed nearby,
using the NINA Vanndata fisk dataset — a national DarwinCore archive of ~85 000
georeferenced freshwater fish observations (updated April 2026).

Data source
-----------
- **Provider**: Norsk institutt for naturforskning (NINA)
- **URL**: https://ipt.nina.no/archive.do?r=vanninfofisk
- **Format**: ZIP with an occurrence.txt TSV file (WGS84 coordinates)
- **Coverage**: Norway-wide, all records have lat/lon, coordinate precision ~100 m
- **Top species**: Salmo trutta (trout), Perca fluviatilis (perch),
  Salvelinus alpinus (char), Esox lucius (pike), Abramis brama (bream)

Output columns (raw data for JS-side scoring)
---------------------------------------------
fish_species_count  — total unique species observed within the buffer
fish_genera_mask    — integer bitmask of which prized genera are present
                      (bit ``i`` set when ``PRIZED_GENERA[i]`` is found nearby)

JS-side scoring
---------------
The user toggles which prized genera they care about.  Score = fraction of
desired genera that are present at the lake, mapped to a 1–5 level:
  0.00        → TERRIBLE
  (0.00–0.25] → POOR
  (0.25–0.50] → FAIR
  (0.50–0.75] → GOOD
  (0.75–1.00] → EXCELLENT

When no genera are selected the fishing dimension is excluded from the
composite tentability score.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from telttur.config import FishingConfig
from telttur.geo import CRS_UTM33, CRS_WGS84, EPSG_CODE_UTM33
from telttur.lakes import LakeCols

_NINA_URL = "https://ipt.nina.no/archive.do?r=vanninfofisk"
_NINA_ARCHIVE_NAME = "vanninfofisk.zip"

# Ordered list of (genus, user-facing label) pairs for the prized game fish.
# The list position is the bit index used in the fish_genera_mask column.
_PRIZED_GENERA_LIST: list[tuple[str, str]] = [
    ("Salmo", "Trout/Salmon"),  # bit 0
    ("Salvelinus", "Char"),  # bit 1
    ("Thymallus", "Grayling"),  # bit 2
    ("Esox", "Pike"),  # bit 3
    ("Perca", "Perch"),  # bit 4
    ("Coregonus", "Whitefish"),  # bit 5
]

# Exported to the frontend config block so JavaScript can render genus labels
# and interpret the bitmask bits.
PRIZED_GENERA: list[dict[str, object]] = [
    {"code": i, "genus": genus, "label": label}
    for i, (genus, label) in enumerate(_PRIZED_GENERA_LIST)
]

_GENUS_TO_BIT: dict[str, int] = {genus: i for i, (genus, _) in enumerate(_PRIZED_GENERA_LIST)}


def _ensure_nina_archive(data_dir: Path, timeout_s: float) -> Path:
    """Return path to the cached NINA archive, downloading it if absent."""
    archive_path = data_dir / _NINA_ARCHIVE_NAME
    if archive_path.exists():
        print(f"  Using cached NINA archive: {archive_path}")
        return archive_path

    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(_NINA_URL, timeout=timeout_s)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to download NINA fish data: {exc}") from exc

    try:
        archive_path.write_bytes(resp.content)
    except OSError as exc:
        archive_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to save NINA fish archive: {exc}") from exc

    return archive_path


def fetch_nina_fish_observations(data_dir: Path, timeout_s: float = 60.0) -> gpd.GeoDataFrame:
    """Load the NINA freshwater fish occurrence archive, downloading it if not cached.

    Returns a GeoDataFrame (UTM33) with columns:
      geometry           — Point
      scientific_name    — species name string

    Raises ``RuntimeError`` on network or parsing errors.
    """
    archive_path = _ensure_nina_archive(data_dir, timeout_s)

    try:
        with zipfile.ZipFile(archive_path) as zf, zf.open("occurrence.txt") as f:
            df = pd.read_csv(
                f,
                sep="\t",
                usecols=["scientificName", "decimalLatitude", "decimalLongitude"],
                dtype=str,
            )
    except Exception as exc:
        raise RuntimeError(f"Failed to parse NINA fish archive: {exc}") from exc

    df = df.dropna(subset=["decimalLatitude", "decimalLongitude", "scientificName"])
    df["decimalLatitude"] = pd.to_numeric(df["decimalLatitude"], errors="coerce")
    df["decimalLongitude"] = pd.to_numeric(df["decimalLongitude"], errors="coerce")
    df = df.dropna(subset=["decimalLatitude", "decimalLongitude"])

    df["scientific_name"] = df["scientificName"].str.strip()

    geometry = [
        Point(lon, lat)
        for lon, lat in zip(df["decimalLongitude"], df["decimalLatitude"], strict=True)
    ]
    gdf = gpd.GeoDataFrame(
        df[["scientific_name"]],
        geometry=geometry,
        crs=CRS_WGS84,
    )
    return gdf.to_crs(CRS_UTM33)


def _build_genera_mask(species_names: pd.Series) -> int:
    """Build a bitmask of prized genera present in a collection of species names."""
    mask = 0
    for name in species_names:
        genus = name.split()[0] if name else ""
        bit = _GENUS_TO_BIT.get(genus)
        if bit is not None:
            mask |= 1 << bit
    return mask


def score_fishing(
    lakes: gpd.GeoDataFrame,
    fish_obs: gpd.GeoDataFrame,
    config: FishingConfig,
) -> gpd.GeoDataFrame:
    """Score each lake based on fish species observations within a buffer.

    Uses a spatial join between buffered lake polygons (UTM33) and fish
    observation points to count unique species per lake and record which
    prized genera are present.

    Added columns:
      fish_species_count  — total unique species observed within buffer
      fish_genera_mask    — integer bitmask of which prized genera are present
    """
    lakes = lakes.copy()

    # Work in UTM33 for accurate buffering
    lakes_utm = lakes.to_crs(CRS_UTM33) if lakes.crs.to_epsg() != EPSG_CODE_UTM33 else lakes
    buffered = lakes_utm.copy()
    buffered["geometry"] = buffered.geometry.buffer(config.buffer_m)

    # Spatial join: find which fish observations fall within each lake's buffer
    fish_in_buffer = gpd.sjoin(
        fish_obs,
        buffered[["geometry"]].reset_index(names="lake_idx"),
        how="inner",
        predicate="within",
    )

    # Category 3: no observed fish within any lake buffer is a real zero, not an error.
    if not fish_in_buffer.empty:
        species_per_lake = (
            fish_in_buffer.groupby("lake_idx")["scientific_name"]
            .nunique()
            .rename(LakeCols.FISH_SPECIES_COUNT)
        )
        genera_mask_per_lake = (
            fish_in_buffer.groupby("lake_idx")["scientific_name"]
            .apply(_build_genera_mask)
            .rename(LakeCols.FISH_GENERA_MASK)
        )
        agg = pd.concat([species_per_lake, genera_mask_per_lake], axis=1)
    else:
        agg = pd.DataFrame(
            columns=[LakeCols.FISH_SPECIES_COUNT, LakeCols.FISH_GENERA_MASK],
            dtype=int,
        )

    lakes[LakeCols.FISH_SPECIES_COUNT] = (
        agg[LakeCols.FISH_SPECIES_COUNT].reindex(lakes.index).fillna(0).astype(int)
    )
    lakes[LakeCols.FISH_GENERA_MASK] = (
        agg[LakeCols.FISH_GENERA_MASK].reindex(lakes.index).fillna(0).astype(int)
    )

    return lakes
