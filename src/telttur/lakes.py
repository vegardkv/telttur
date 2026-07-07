"""Lake extraction from N50 Kartdata."""

from enum import StrEnum
from pathlib import Path

import fiona
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from telttur.config import BBox
from telttur.geo import (
    CRS_UTM33,
    CRS_WGS84,
    bbox_to_utm33,
    find_objtype_column,
    read_n50_layer,
)


class LakeCols(StrEnum):
    # Core geometry columns
    AREA_M2 = "area_m2"
    AREA_DISPLAY = "area_display"

    # Accessibility — raw data (score computed in JS)
    ROAD_DISTANCE_M = "road_distance_m"
    TRANSIT_DISTANCE_M = "transit_distance_m"

    # Cabin density — raw data (score computed in JS)
    BUILDING_COUNT = "building_count"
    BUILDING_DENSITY = "building_density"

    # AR5 land use — raw data (score computed in JS)
    INDUSTRIAL_DISTANCE_M = "industrial_distance_m"
    RESIDENTIAL_DISTANCE_M = "residential_distance_m"

    # Fishing — raw data (score computed in JS)
    FISH_SPECIES_COUNT = "fish_species_count"
    FISH_GENERA_MASK = "fish_genera_mask"

    # Elevation gain — raw data (score computed in JS)
    ELEVATION_GAIN_M = "elevation_gain_m"
    TRANSIT_ELEVATION_GAIN_M = "transit_elevation_gain_m"

    # Restrictions bitmask — bit 0 = drinking-water source (drikkevann)
    RESTRICTIONS_MASK = "restrictions_mask"


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


def extract_lakes(
    gdb_paths: list[Path],
    bbox: BBox,
    simplify_tolerance_m: float = 0,
) -> gpd.GeoDataFrame:
    """Extract lake polygons from N50 FGDB files, clipped to bbox."""
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        lake_layers = find_lake_layers(gdb_path)
        if not lake_layers:
            print(f"  No lake/water layers found in {gdb_path.name}")
            continue

        for layer_name in lake_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = read_n50_layer(
                gdb_path, layer_name, utm_bounds, geom_types=("Polygon", "MultiPolygon")
            )

            # Filter for lake-type features if there's an object type column
            type_col = find_objtype_column(gdf)
            if type_col:
                lake_types = ["Innsjø", "Innsjo", "InnsjøRegulert", "InnsjoRegulert", "Vann"]
                mask = gdf[type_col].str.lower().isin([t.lower() for t in lake_types])
                gdf = gdf[mask]

            frames.append(gdf)

    if not frames:
        # Category 1: N50 always ships a lake/water layer, so finding none means the
        # download is incomplete/corrupt. (Empty rows after clipping is the no-lakes case.)
        names = ", ".join(p.name for p in gdb_paths)
        raise RuntimeError(
            f"No lake/water layer found in N50 data ({names}); the N50 download may be "
            "incomplete. Delete the cache and re-run."
        )

    lakes = pd.concat(frames, ignore_index=True)
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
            f"  Removed {before - len(lakes)} lakes below {min_lake_area_m2:.0f} m²"
            f"({len(lakes)} remaining)"
        )
    return lakes
