"""Lake tentability scoring package.

Each scoring dimension lives in its own module and is an equal citizen:
all can be independently enabled/disabled via config. Each dimension module
exposes:
  SCORE_COLUMN  — name of the integer score column added to the lakes GeoDataFrame
  POPUP_FIELDS  — list of (column_name, display_label) tuples for map popups

Public API:
  process_scoring()            — full scoring pipeline (all enabled dimensions)
  compute_tentability()        — composite score from active dimension columns
  get_scoring_popup_fields()   — popup fields for scoring columns present in lakes
  TentabilityLevel, LEVEL_NAMES, LEVEL_COLORS  — shared scale constants
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd

from telttur.scoring import accessibility, ar5_land_use, cabin_density
from telttur.scoring.common import (
    LEVEL_COLORS,
    LEVEL_NAMES,
    PopupField,
    TentabilityLevel,
    _print_distribution,
    compute_tentability,
)

if TYPE_CHECKING:
    from telttur.config import BBox, ScoringConfig

__all__ = [
    "TentabilityLevel",
    "LEVEL_NAMES",
    "LEVEL_COLORS",
    "compute_tentability",
    "process_scoring",
    "get_scoring_popup_fields",
]

# All dimension modules in display order (used for popup field collection)
_DIMENSION_MODULES = [cabin_density, accessibility, ar5_land_use]


def get_scoring_popup_fields(lakes: gpd.GeoDataFrame) -> list[PopupField]:
    """Return (column, label) pairs for scoring columns present in lakes.

    Only returns fields whose columns are actually in the GeoDataFrame, so
    dimensions that were disabled (and therefore never added their columns)
    are automatically excluded from popups.
    """
    result: list[PopupField] = []
    for module in _DIMENSION_MODULES:
        for col, alias in module.POPUP_FIELDS:
            if col in lakes.columns:
                result.append((col, alias))
    return result


def process_scoring(
    gdb_paths: list[Path],
    bbox: BBox,
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    config: ScoringConfig,
    excluded_road_types: list[str] | None = None,
) -> gpd.GeoDataFrame:
    """Full scoring pipeline: run enabled dimensions then compute composite tentability.

    Each dimension is run only when its ``enabled`` flag is True. The composite
    tentability score is the worst (minimum) of all enabled dimension scores.
    """
    dimension_score_columns: list[str] = []

    # --- Cabin density ---
    if config.cabin_density.enabled:
        print("Extracting buildings for cabin density scoring...")
        buildings = cabin_density.extract_buildings(gdb_paths, bbox)
        print(f"  Found {len(buildings)} building features")

        if buildings.empty:
            print("  No buildings found — skipping cabin density dimension")
            lakes = lakes.copy()
            lakes["building_count"] = 0
            lakes[cabin_density.SCORE_COLUMN] = int(TentabilityLevel.EXCELLENT)
            lakes["cabin_density_level"] = LEVEL_NAMES[TentabilityLevel.EXCELLENT]
        else:
            print(f"Scoring cabin density ({config.cabin_density.buffer_m} m buffer)...")
            lakes = cabin_density.score_cabin_density(lakes, buildings, config.cabin_density)
            _print_distribution("Cabin density", lakes, cabin_density.SCORE_COLUMN)
        dimension_score_columns.append(cabin_density.SCORE_COLUMN)
    else:
        print("Cabin density scoring disabled — skipping")

    # --- Accessibility ---
    if config.accessibility.enabled:
        print("Scoring accessibility (distance to nearest drivable road)...")
        lakes = accessibility.score_accessibility(
            lakes, road_lines, config.accessibility, excluded_road_types
        )
        _print_distribution("Accessibility", lakes, accessibility.SCORE_COLUMN)
        dimension_score_columns.append(accessibility.SCORE_COLUMN)
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
        _print_distribution("AR5 land use", lakes, ar5_land_use.SCORE_COLUMN)
        dimension_score_columns.append(ar5_land_use.SCORE_COLUMN)
    else:
        print("AR5 land use scoring disabled — skipping")

    # --- Composite ---
    print("Computing composite tentability score (worst dimension wins)...")
    lakes = compute_tentability(lakes, dimension_score_columns)
    _print_distribution("Tentability", lakes, "tentability_score")

    return lakes
