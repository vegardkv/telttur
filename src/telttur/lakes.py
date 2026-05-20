"""Lake extraction from N50 Kartdata."""

from enum import StrEnum
from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox

CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"


class LakeCols(StrEnum):
    # Core geometry columns
    AREA_M2 = "area_m2"
    AREA_DISPLAY = "area_display"

    # Accessibility — raw data (score computed in JS)
    ROAD_DISTANCE_M = "road_distance_m"

    # Cabin density — raw data (score computed in JS)
    BUILDING_COUNT = "building_count"
    BUILDING_DENSITY = "building_density"

    # AR5 land use — raw data (score computed in JS)
    INDUSTRIAL_DISTANCE_M = "industrial_distance_m"
    RESIDENTIAL_DISTANCE_M = "residential_distance_m"

    # Fishing — score computed in Python (not recomputable in JS)
    FISH_SPECIES_COUNT = "fish_species_count"
    FISH_PRIZED_COUNT = "fish_prized_count"
    FISHING_SCORE = "fishing_score"
    FISHING_LEVEL = "fishing_level"


def find_lake_layers(gdb_path: Path) -> list[str]:
    """List layers in a .gdb that likely contain lake/water data."""
    all_layers = fiona.listlayers(str(gdb_path))
    water_keywords = ["innsj", "vann", "water", "arealdekke"]
    matches = [
        layer
        for layer in all_layers
        if any(kw in layer.lower() for kw in water_keywords) and "omrade" in layer.lower()
    ]
    if not matches:
        print(f"  Available layers in {gdb_path.name}: {all_layers}")
    return matches


def _bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    """Convert WGS84 bbox to UTM33 bounds."""
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    bbox_utm = bbox_gdf.to_crs(CRS_UTM33)
    b = bbox_utm.total_bounds
    return (b[0], b[1], b[2], b[3])


def extract_lakes(
    gdb_paths: list[Path],
    bbox: BBox,
    simplify_tolerance_m: float = 0,
) -> gpd.GeoDataFrame:
    """Extract lake polygons from N50 FGDB files, clipped to bbox."""
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = _bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        lake_layers = find_lake_layers(gdb_path)
        if not lake_layers:
            print(f"  No lake/water layers found in {gdb_path.name}")
            continue

        for layer_name in lake_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name, bbox=utm_bounds)

            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif str(gdf.crs) != CRS_UTM33:
                gdf = gdf.to_crs(CRS_UTM33)

            # Filter for lake-type features if there's an object type column
            type_col = None
            for candidate in ["objtype", "OBJTYPE", "objType"]:
                if candidate in gdf.columns:
                    type_col = candidate
                    break

            if type_col:
                lake_types = ["Innsjø", "Innsjo", "InnsjøRegulert", "InnsjoRegulert", "Vann"]
                mask = gdf[type_col].str.lower().isin([t.lower() for t in lake_types])
                gdf = gdf[mask]

            # Keep only polygon geometries
            gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry"], crs=CRS_WGS84)

    lakes = gpd.pd.concat(frames, ignore_index=True)
    lakes = gpd.GeoDataFrame(lakes, crs=CRS_UTM33)

    # Clip to bbox (exact clip after bbox pre-filter)
    clip_box = box(*utm_bounds)
    lakes = lakes.clip(clip_box)

    if simplify_tolerance_m > 0:
        lakes["geometry"] = lakes.geometry.simplify(simplify_tolerance_m)

    lakes[LakeCols.AREA_M2] = lakes.geometry.area

    return lakes.to_crs(CRS_WGS84)


def process_lakes(
    gdb_paths: list[Path],
    bbox: BBox,
    simplify_tolerance_m: float = 0,
    min_lake_area_m2: float = 0.0,
) -> gpd.GeoDataFrame:
    """Full pipeline: extract lake polygons from N50 FGDB files."""
    print("Extracting lakes...")
    lakes = extract_lakes(gdb_paths, bbox, simplify_tolerance_m)
    print(f"  Found {len(lakes)} lake features")
    if min_lake_area_m2 > 0:
        before = len(lakes)
        lakes = lakes[lakes[LakeCols.AREA_M2] >= min_lake_area_m2].reset_index(drop=True)
        print(
            f"  Removed {before - len(lakes)} lakes below {min_lake_area_m2:.0f} m² ({len(lakes)} remaining)"
        )
    return lakes
