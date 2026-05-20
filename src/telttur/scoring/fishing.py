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

Scoring logic
-------------
Each lake is scored on two components combined into a 1–5 scale:

1. **Species richness** — number of unique fish species observed within a
   configurable buffer around the lake (default 500 m).  More species → higher
   potential for varied fishing.

2. **Prized species bonus** — presence of recognised game fish (trout, char,
   pike, perch, grayling) boosts the score.  These are the species most valued
   by recreational anglers in Norway.

Score mapping (species_count + bonus points):
  0 pts  → TERRIBLE (no fish data at all)
  1–2    → POOR
  3–4    → FAIR
  5–7    → GOOD
  8+     → EXCELLENT
"""

from __future__ import annotations

import io
import zipfile

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from telttur.config import FishingConfig
from telttur.lakes import LakeCols
from telttur.scoring.common import (
    CRS_UTM33,
    CRS_WGS84,
    LEVEL_NAMES,
    TentabilityLevel,
)

SCORE_COLUMN = LakeCols.FISHING_SCORE

_NINA_URL = "https://ipt.nina.no/archive.do?r=vanninfofisk"

# Scientific names (genus-level prefix is enough for variants / subspecies)
# of species most valued by Norwegian recreational anglers.
_PRIZED_GENERA: frozenset[str] = frozenset(
    {
        "Salmo",  # trout, salmon
        "Salvelinus",  # char (røye)
        "Thymallus",  # grayling (harr)
        "Esox",  # pike (gjedde)
        "Perca",  # perch (abbor)
        "Sander",  # pikeperch / zander (gjeddeabbor)
        "Coregonus",  # whitefish (sik, lagesild)
        "Hucho",  # huchen (not common, but prized)
    }
)


def _is_prized(scientific_name: str) -> bool:
    genus = scientific_name.split()[0] if scientific_name else ""
    return genus in _PRIZED_GENERA


def fetch_nina_fish_observations(timeout_s: float = 60.0) -> gpd.GeoDataFrame:
    """Download and parse the NINA freshwater fish occurrence archive.

    Returns a GeoDataFrame (WGS84) with columns:
      geometry           — Point from decimalLatitude / decimalLongitude
      scientific_name    — species name
      is_prized          — True if the species is a recognised game fish

    Raises ``RuntimeError`` on network or parsing errors.
    """
    try:
        resp = requests.get(_NINA_URL, timeout=timeout_s)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to download NINA fish data: {exc}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open("occurrence.txt") as f:
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

    # Keep only the first word of the scientific name (genus) and the full name
    df["scientific_name"] = df["scientificName"].str.strip()
    df["is_prized"] = df["scientific_name"].apply(_is_prized)

    geometry = [Point(lon, lat) for lon, lat in zip(df["decimalLongitude"], df["decimalLatitude"])]
    gdf = gpd.GeoDataFrame(
        df[["scientific_name", "is_prized"]],
        geometry=geometry,
        crs=CRS_WGS84,
    )
    return gdf.to_crs(CRS_UTM33)


def _compute_score(species_count: int, prized_count: int) -> int:
    """Map species richness + prized bonus to a TentabilityLevel integer."""
    if species_count == 0:
        return int(TentabilityLevel.TERRIBLE)
    points = species_count + prized_count
    if points >= 8:
        return int(TentabilityLevel.EXCELLENT)
    if points >= 5:
        return int(TentabilityLevel.GOOD)
    if points >= 3:
        return int(TentabilityLevel.FAIR)
    if points >= 1:
        return int(TentabilityLevel.POOR)
    return int(TentabilityLevel.TERRIBLE)


def score_fishing(
    lakes: gpd.GeoDataFrame,
    fish_obs: gpd.GeoDataFrame,
    config: FishingConfig,
) -> gpd.GeoDataFrame:
    """Score each lake based on fish species observations within a buffer.

    Uses a spatial join between buffered lake polygons (UTM33) and fish
    observation points to count unique species per lake.

    Added columns:
      fish_species_count  — unique fish species observed within buffer
      fish_prized_count   — how many of those are prized game fish
      fishing_score       — TentabilityLevel integer (1 = Terrible … 5 = Excellent)
      fishing_level       — human-readable level name
    """
    lakes = lakes.copy()

    # Work in UTM33 for accurate buffering
    lakes_utm = lakes.to_crs(CRS_UTM33) if lakes.crs.to_epsg() != 25833 else lakes
    buffered = lakes_utm.copy()
    buffered["geometry"] = buffered.geometry.buffer(config.buffer_m)

    # Spatial join: find which fish observations fall within each lake's buffer
    fish_in_buffer = gpd.sjoin(
        fish_obs,
        buffered[["geometry"]].reset_index(names="lake_idx"),
        how="inner",
        predicate="within",
    )

    # Aggregate per lake: unique species count and prized count
    if not fish_in_buffer.empty:
        species_per_lake = (
            fish_in_buffer.groupby("lake_idx")["scientific_name"]
            .nunique()
            .rename(LakeCols.FISH_SPECIES_COUNT)
        )
        prized_per_lake = (
            fish_in_buffer[fish_in_buffer["is_prized"]]
            .groupby("lake_idx")["scientific_name"]
            .nunique()
            .rename(LakeCols.FISH_PRIZED_COUNT)
        )
        agg = pd.concat([species_per_lake, prized_per_lake], axis=1).fillna(0).astype(int)
    else:
        agg = pd.DataFrame(
            columns=[LakeCols.FISH_SPECIES_COUNT, LakeCols.FISH_PRIZED_COUNT],
            dtype=int,
        )

    lakes[LakeCols.FISH_SPECIES_COUNT] = (
        agg[LakeCols.FISH_SPECIES_COUNT].reindex(lakes.index).fillna(0).astype(int)
    )
    lakes[LakeCols.FISH_PRIZED_COUNT] = (
        agg[LakeCols.FISH_PRIZED_COUNT].reindex(lakes.index).fillna(0).astype(int)
    )
    lakes[SCORE_COLUMN] = [
        _compute_score(s, p)
        for s, p in zip(lakes[LakeCols.FISH_SPECIES_COUNT], lakes[LakeCols.FISH_PRIZED_COUNT])
    ]
    lakes[LakeCols.FISHING_LEVEL] = lakes[SCORE_COLUMN].map(LEVEL_NAMES)

    return lakes
