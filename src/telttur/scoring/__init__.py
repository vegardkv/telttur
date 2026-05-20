"""Lake tentability scoring package.

Each scoring dimension lives in its own module and is an equal citizen:
all can be independently enabled/disabled via config. Each dimension module
computes raw data columns (distances, densities). Threshold-based score
conversion is handled by the JavaScript frontend, which allows interactive
slider-driven recomputation.

Exception: the fishing dimension computes its score in Python because the
scoring logic requires species-level metadata that is not available in JS.

Public API:
  process_scoring()            — full scoring pipeline (all enabled dimensions)
  TentabilityLevel, LEVEL_NAMES, LEVEL_COLORS  — shared scale constants
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd

from telttur.lakes import LakeCols
from telttur.scoring import accessibility, ar5_land_use, cabin_density, fishing
from telttur.scoring.common import (
    LEVEL_COLORS,
    LEVEL_NAMES,
    TentabilityLevel,
    _print_distribution,
)

if TYPE_CHECKING:
    from telttur.config import BBox, ScoringConfig

__all__ = [
    "TentabilityLevel",
    "LEVEL_NAMES",
    "LEVEL_COLORS",
    "process_scoring",
]


def process_scoring(
    gdb_paths: list[Path],
    bbox: BBox,
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    config: ScoringConfig,
) -> gpd.GeoDataFrame:
    """Full scoring pipeline: run enabled dimensions to compute raw data columns.

    Each dimension is run only when its ``enabled`` flag is True. Raw data
    columns (distances, densities) are computed here; threshold-based score
    conversion is handled by the JavaScript frontend.

    Exception: the fishing dimension computes its score in Python because
    the scoring logic requires species-level metadata unavailable in JS.
    """

    # --- Cabin density ---
    if config.cabin_density.enabled:
        print("Extracting buildings for cabin density scoring...")
        buildings = cabin_density.extract_buildings(gdb_paths, bbox)
        print(f"  Found {len(buildings)} building features")

        if buildings.empty:
            print("  No buildings found — all lakes get zero building density")
            lakes = lakes.copy()
            lakes[LakeCols.BUILDING_COUNT] = 0
            lakes[LakeCols.BUILDING_DENSITY] = 0.0
        else:
            print(f"Scoring cabin density ({config.cabin_density.buffer_m} m buffer)...")
            lakes = cabin_density.score_cabin_density(lakes, buildings, config.cabin_density)
    else:
        print("Cabin density scoring disabled — skipping")

    # --- Accessibility ---
    if config.accessibility.enabled:
        print("Scoring accessibility (distance to nearest drivable road)...")
        lakes = accessibility.score_accessibility(
            lakes, road_lines, config.accessibility, config.accessibility.excluded_road_types
        )
    else:
        print("Accessibility scoring disabled — skipping")

    # --- AR5 land use proximity ---
    if config.ar5_land_use.enabled:
        print("Scoring AR5 land use proximity (industrial / residential zones)...")
        industrial_polygons, residential_polygons = ar5_land_use.fetch_ar5_land_use_polygons(
            gdb_paths, bbox, config.ar5_land_use
        )
        lakes = ar5_land_use.score_ar5_land_use(
            lakes, industrial_polygons, residential_polygons, config.ar5_land_use
        )
    else:
        print("AR5 land use scoring disabled — skipping")

    # --- Fishing suitability (score computed in Python — not recomputable in JS) ---
    if config.fishing.enabled:
        print("Downloading NINA freshwater fish observations...")
        try:
            fish_obs = fishing.fetch_nina_fish_observations()
            print(f"  Loaded {len(fish_obs)} fish occurrence records")
            print(f"Scoring fishing suitability ({config.fishing.buffer_m} m buffer)...")
            lakes = fishing.score_fishing(lakes, fish_obs, config.fishing)
            _print_distribution("Fishing", lakes, fishing.SCORE_COLUMN)
        except RuntimeError as exc:
            print(f"  WARNING: Fishing scoring skipped — {exc}")
    else:
        print("Fishing scoring disabled — skipping")

    return lakes
