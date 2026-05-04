"""Lake tentability scoring: composite score from multiple dimensions.

Each dimension is scored on a 5-level scale (Terrible → Excellent).  The
composite tentability score is the *worst* (minimum) of all dimension scores,
so a single bad dimension can drag the overall score down.

Dimensions currently implemented:
  - Cabin density   : count of residential/cabin buildings within a shore buffer
  - Accessibility   : distance to the nearest drivable road

Dimensions designed for future extension:
  - Steepness       : slope of terrain surrounding the lake shore (requires DTM)
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import AccessibilityThresholds, BBox, CabinDensityThresholds, ScoringConfig

CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"

# Non-motorised road categories — excluded from accessibility scoring because
# they cannot be reached by car.
_NON_MOTORIZED: set[str] = {"gangOgSykkelveg", "sti"}


# ---------------------------------------------------------------------------
# Tentability level definitions
# ---------------------------------------------------------------------------


class TentabilityLevel(IntEnum):
    TERRIBLE = 1
    POOR = 2
    FAIR = 3
    GOOD = 4
    EXCELLENT = 5


LEVEL_NAMES: dict[int, str] = {
    TentabilityLevel.TERRIBLE: "Terrible",
    TentabilityLevel.POOR: "Poor",
    TentabilityLevel.FAIR: "Fair",
    TentabilityLevel.GOOD: "Good",
    TentabilityLevel.EXCELLENT: "Excellent",
}

# Diverging red→green palette (matching road category palette conventions)
LEVEL_COLORS: dict[int, str] = {
    TentabilityLevel.TERRIBLE: "#d73027",
    TentabilityLevel.POOR: "#fc8d59",
    TentabilityLevel.FAIR: "#fee08b",
    TentabilityLevel.GOOD: "#91cf60",
    TentabilityLevel.EXCELLENT: "#1a9850",
}


# ---------------------------------------------------------------------------
# Building extraction (for cabin density scoring)
# ---------------------------------------------------------------------------

# Norwegian building type codes (bygningstype) that indicate habitation:
#   100–199: Residential buildings, including:
#     161–169: Cabins/fritidsboliger (dominant in mountain areas)
#     111–119: Single-family homes, 121–129: Two-family homes, etc.
_RESIDENTIAL_MIN = 100
_RESIDENTIAL_MAX = 199


def _bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    b = bbox_gdf.to_crs(CRS_UTM33).total_bounds
    return (b[0], b[1], b[2], b[3])


def find_building_layers(gdb_path: Path) -> list[str]:
    """List layers in a .gdb that contain building point data."""
    all_layers = fiona.listlayers(str(gdb_path))
    return [
        layer
        for layer in all_layers
        if any(kw in layer.lower() for kw in ("bygning", "building"))
        and "posisjon" in layer.lower()
    ]


def extract_buildings(gdb_paths: list[Path], bbox: BBox) -> gpd.GeoDataFrame:
    """Extract residential/cabin building points from N50 FGDB files, clipped to bbox.

    Filters to objtype == 'Bygning' and bygningstype 100–199 (residential/cabins).
    This excludes masts, tanks, industrial buildings, barns, churches, etc.
    """
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = _bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        for layer_name in find_building_layers(gdb_path):
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name, bbox=utm_bounds)

            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif str(gdf.crs) != CRS_UTM33:
                gdf = gdf.to_crs(CRS_UTM33)

            if "objtype" in gdf.columns:
                gdf = gdf[gdf["objtype"] == "Bygning"]
            if "bygningstype" in gdf.columns:
                gdf = gdf[gdf["bygningstype"].between(_RESIDENTIAL_MIN, _RESIDENTIAL_MAX)]

            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry"], crs=CRS_UTM33)

    buildings = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs=CRS_UTM33)
    return buildings.clip(box(*utm_bounds))


# ---------------------------------------------------------------------------
# Dimension scoring functions
# ---------------------------------------------------------------------------


def score_cabin_density(
    lakes: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    buffer_m: float,
    thresholds: CabinDensityThresholds,
) -> gpd.GeoDataFrame:
    """Score each lake by cabin/building density near its shore.

    Density is defined as ``building_count / sqrt(area_m2)``, which normalises
    for lake size so that a large remote lake with a handful of cabins is not
    penalised as harshly as a small lake surrounded by the same number of
    buildings.  ``sqrt(area_m2)`` is used as a proxy for shoreline length.

    The ``area_m2`` column must already be present on *lakes* (added by
    ``process_lakes``).

    Added columns:
      building_count       — number of buildings within the buffer
      building_density     — building_count / sqrt(area_m2), rounded to 4 dp
      cabin_density_score  — TentabilityLevel integer (1 = Terrible … 5 = Excellent)
      cabin_density_level  — human-readable level name
    """
    import math

    lakes = lakes.copy()
    lakes_utm = lakes.to_crs(CRS_UTM33).copy()
    buildings_utm = (
        buildings if str(buildings.crs) == CRS_UTM33 else buildings.to_crs(CRS_UTM33)
    )

    # Buffer all lake polygons at once, then count buildings inside each buffer
    lakes_utm["_buf"] = lakes_utm.geometry.buffer(buffer_m)
    lake_buffers = (
        lakes_utm[["_buf"]].set_geometry("_buf").rename_geometry("geometry")
    )
    lake_buffers.index = lakes_utm.index

    joined = gpd.sjoin(lake_buffers, buildings_utm[["geometry"]], how="left", predicate="contains")
    building_count = joined.groupby(joined.index)["index_right"].count()
    lakes["building_count"] = lakes.index.map(building_count).fillna(0).astype(int)

    # Normalise by sqrt(area_m2) — use area_m2 when available, fall back to
    # computing area in UTM to avoid zero-division.
    if "area_m2" in lakes.columns:
        area_m2 = lakes["area_m2"]
    else:
        area_m2 = lakes.to_crs(CRS_UTM33).geometry.area

    sqrt_area = area_m2.apply(lambda a: math.sqrt(max(a, 1.0)))
    lakes["building_density"] = (lakes["building_count"] / sqrt_area).round(4)

    def _score(density: float) -> int:
        if density <= thresholds.excellent:
            return int(TentabilityLevel.EXCELLENT)
        elif density <= thresholds.good:
            return int(TentabilityLevel.GOOD)
        elif density <= thresholds.fair:
            return int(TentabilityLevel.FAIR)
        elif density <= thresholds.poor:
            return int(TentabilityLevel.POOR)
        return int(TentabilityLevel.TERRIBLE)

    lakes["cabin_density_score"] = lakes["building_density"].apply(_score)
    lakes["cabin_density_level"] = lakes["cabin_density_score"].map(LEVEL_NAMES)
    return lakes


def score_accessibility(
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    thresholds: AccessibilityThresholds,
    excluded_road_types: list[str] | None = None,
) -> gpd.GeoDataFrame:
    """Score each lake by distance to the nearest drivable road.

    Road types listed in *excluded_road_types* are excluded because they
    cannot be reached by car.  Defaults to the module-level ``_NON_MOTORIZED``
    set when not provided.

    Added columns:
      road_distance_m      — metres to nearest drivable road (rounded to 1 dp)
      accessibility_score  — TentabilityLevel integer (1 = Terrible … 5 = Excellent)
      accessibility_level  — human-readable level name
    """
    lakes = lakes.copy()

    excluded = set(excluded_road_types) if excluded_road_types is not None else _NON_MOTORIZED
    drivable = (
        road_lines[~road_lines["category"].isin(excluded)]
        if "category" in road_lines.columns
        else road_lines
    )

    if drivable.empty:
        lakes["road_distance_m"] = float("inf")
        lakes["accessibility_score"] = int(TentabilityLevel.TERRIBLE)
        lakes["accessibility_level"] = LEVEL_NAMES[TentabilityLevel.TERRIBLE]
        return lakes

    lakes_utm = lakes.to_crs(CRS_UTM33)
    roads_utm = drivable[["geometry"]].to_crs(CRS_UTM33)

    # sjoin_nearest computes minimum Euclidean distance (metres in UTM33).
    # Duplicate rows arise when multiple roads tie for nearest — take the min.
    joined = gpd.sjoin_nearest(
        lakes_utm[["geometry"]],
        roads_utm,
        how="left",
        distance_col="road_distance_m",
    )
    distances = joined.groupby(joined.index)["road_distance_m"].min()
    lakes["road_distance_m"] = (
        lakes.index.map(distances).fillna(float("inf")).round(1)
    )

    def _score(d: float) -> int:
        if d <= thresholds.excellent:
            return int(TentabilityLevel.EXCELLENT)
        elif d <= thresholds.good:
            return int(TentabilityLevel.GOOD)
        elif d <= thresholds.fair:
            return int(TentabilityLevel.FAIR)
        elif d <= thresholds.poor:
            return int(TentabilityLevel.POOR)
        return int(TentabilityLevel.TERRIBLE)

    lakes["accessibility_score"] = lakes["road_distance_m"].apply(_score)
    lakes["accessibility_level"] = lakes["accessibility_score"].map(LEVEL_NAMES)
    return lakes


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def compute_tentability(
    lakes: gpd.GeoDataFrame,
    dimension_columns: list[str],
) -> gpd.GeoDataFrame:
    """Compute the composite tentability score as the *worst* of all dimensions.

    Added columns:
      tentability_score  — integer 1–5 (min of all dimension scores)
      tentability_level  — human-readable name (e.g. "Good")
      tentability_color  — hex colour for map display
    """
    lakes = lakes.copy()
    present = [c for c in dimension_columns if c in lakes.columns]
    lakes["tentability_score"] = (
        lakes[present].min(axis=1).astype(int) if present else int(TentabilityLevel.FAIR)
    )
    lakes["tentability_level"] = lakes["tentability_score"].map(LEVEL_NAMES)
    lakes["tentability_color"] = lakes["tentability_score"].map(LEVEL_COLORS)
    return lakes


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_DIMENSION_COLUMNS = ["cabin_density_score", "accessibility_score"]


def process_scoring(
    gdb_paths: list[Path],
    bbox: BBox,
    lakes: gpd.GeoDataFrame,
    road_lines: gpd.GeoDataFrame,
    config: ScoringConfig,
    excluded_road_types: list[str] | None = None,
) -> gpd.GeoDataFrame:
    """Full scoring pipeline: score all dimensions then compute composite tentability.

    Steps:
      1. Extract buildings → score cabin density
      2. Score accessibility (distance to nearest drivable road)
      3. Compute composite tentability score (worst dimension wins)
    """
    # --- Cabin density ---
    print("Extracting buildings for cabin density scoring...")
    buildings = extract_buildings(gdb_paths, bbox)
    print(f"  Found {len(buildings)} building features")

    if buildings.empty:
        print("  No buildings found — skipping cabin density dimension")
        lakes = lakes.copy()
        lakes["building_count"] = 0
        lakes["cabin_density_score"] = int(TentabilityLevel.EXCELLENT)
        lakes["cabin_density_level"] = LEVEL_NAMES[TentabilityLevel.EXCELLENT]
    else:
        print(f"Scoring cabin density ({config.building_buffer_m} m buffer)...")
        lakes = score_cabin_density(
            lakes, buildings, config.building_buffer_m, config.cabin_density_thresholds
        )
        _print_distribution("Cabin density", lakes, "cabin_density_score")

    # --- Accessibility ---
    print("Scoring accessibility (distance to nearest drivable road)...")
    lakes = score_accessibility(
        lakes, road_lines, config.accessibility_thresholds, excluded_road_types
    )
    _print_distribution("Accessibility", lakes, "accessibility_score")

    # --- Composite ---
    print("Computing composite tentability score (worst dimension wins)...")
    lakes = compute_tentability(lakes, _DIMENSION_COLUMNS)
    _print_distribution("Tentability", lakes, "tentability_score")

    return lakes


def _print_distribution(label: str, lakes: gpd.GeoDataFrame, col: str) -> None:
    print(f"  {label} distribution:")
    for level in TentabilityLevel:
        count = (lakes[col] == int(level)).sum()
        print(f"    {LEVEL_NAMES[int(level)]}: {count} lakes")
