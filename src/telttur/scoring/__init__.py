"""Lake tentability scoring package.

Each scoring dimension lives in its own module and is an equal citizen:
all can be independently enabled/disabled via config. Each dimension module
computes raw data columns (distances, densities, bitmasks). Threshold-based
score conversion is handled by the JavaScript frontend, which allows
interactive slider-driven recomputation.

Public API:
  process_scoring()            — full scoring pipeline (all enabled dimensions)
  TentabilityLevel, LEVEL_NAMES, LEVEL_COLORS  — shared scale constants
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd

from telttur.elevation import ensure_dem
from telttur.lakes import LakeCols
from telttur.scoring import accessibility, ar5_land_use, cabin_density, fishing
from telttur.scoring.common import (
    LEVEL_COLORS,
    LEVEL_NAMES,
    TentabilityLevel,
)

if TYPE_CHECKING:
    from telttur.config import BBox, ScoringConfig

__all__ = [
    "TentabilityLevel",
    "LEVEL_NAMES",
    "LEVEL_COLORS",
    "process_scoring",
]


def process_scoring(  # noqa: PLR0913
    gdb_paths: list[Path],
    bbox: BBox,
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    config: ScoringConfig,
    data_dir: Path,
) -> gpd.GeoDataFrame:
    """Full scoring pipeline: compute raw data columns for every dimension.

    Raw data columns (distances, densities, bitmasks) are computed here;
    threshold-based score conversion is handled by the JavaScript frontend.
    """

    # --- Cabin density ---
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

    # --- Accessibility ---
    print("Scoring accessibility (distance to nearest drivable road)...")
    dem_path = ensure_dem(data_dir / "dem", bbox)
    lakes = accessibility.score_accessibility(
        lakes,
        road_lines,
        config.accessibility,
        config.accessibility.excluded_road_types,
        dem_path=dem_path,
    )

    # --- AR5 land use proximity ---
    print("Scoring AR5 land use proximity (industrial / residential zones)...")
    industrial_polygons, residential_polygons = ar5_land_use.fetch_ar5_land_use_polygons(
        gdb_paths, bbox, config.ar5_land_use
    )
    lakes = ar5_land_use.score_ar5_land_use(
        lakes, industrial_polygons, residential_polygons, config.ar5_land_use
    )

    # --- Fishing suitability ---
    print("Downloading NINA freshwater fish observations...")
    fish_obs = fishing.fetch_nina_fish_observations(data_dir / "nina")
    print(f"  Loaded {len(fish_obs)} fish occurrence records")
    print(f"Scoring fishing suitability ({config.fishing.buffer_m} m buffer)...")
    lakes = fishing.score_fishing(lakes, fish_obs, config.fishing)
    total = len(lakes)
    with_fish = (lakes[LakeCols.FISH_GENERA_MASK] > 0).sum()
    print(f"  Lakes with at least one prized genus: {with_fish}/{total}")

    return lakes
