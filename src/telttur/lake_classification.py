"""Lake classification by building/cabin density."""

from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox

CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"

# Matrikkelen Bygningspunkt metadata UUID
BUILDING_METADATA_UUID = "24d7e9d1-87f6-45a0-b38e-3447f8d7f9a1"


def find_building_layers(gdb_path: Path) -> list[str]:
    """List layers containing building data."""
    all_layers = fiona.listlayers(str(gdb_path))
    keywords = ["bygning", "building"]
    return [
        layer
        for layer in all_layers
        if any(kw in layer.lower() for kw in keywords) and "posisjon" in layer.lower()
    ]


def _bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    bbox_utm = bbox_gdf.to_crs(CRS_UTM33)
    b = bbox_utm.total_bounds
    return (b[0], b[1], b[2], b[3])


def extract_buildings(
    gdb_paths: list[Path],
    bbox: BBox,
) -> gpd.GeoDataFrame:
    """Extract building points from N50 FGDB files, clipped to bbox."""
    frames: list[gpd.GeoDataFrame] = []

    for gdb_path in gdb_paths:
        building_layers = find_building_layers(gdb_path)
        if not building_layers:
            continue

        for layer_name in building_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name)

            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif str(gdf.crs) != CRS_UTM33:
                gdf = gdf.to_crs(CRS_UTM33)

            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry"], crs=CRS_UTM33)

    buildings = gpd.pd.concat(frames, ignore_index=True)
    buildings = gpd.GeoDataFrame(buildings, crs=CRS_UTM33)

    # Clip to bbox
    utm_bounds = _bbox_to_utm33(bbox)
    clip_box = box(*utm_bounds)
    buildings = buildings.clip(clip_box)

    return buildings


def classify_lakes_by_density(
    lakes: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    buffer_m: float = 500.0,
) -> gpd.GeoDataFrame:
    """Classify lakes by building density around their shores.

    Adds columns:
    - building_count: number of buildings within buffer_m of the lake shore
    - density_class: "low" / "medium" / "high"
    - density_color: color for map visualization
    """
    lakes = lakes.copy()

    # Work in UTM for metric buffering
    lakes_utm = lakes.to_crs(CRS_UTM33)
    buildings_utm = buildings.to_crs(CRS_UTM33) if buildings.crs != CRS_UTM33 else buildings

    counts = []
    for _, lake in lakes_utm.iterrows():
        lake_buffer = lake.geometry.buffer(buffer_m)
        nearby = buildings_utm[buildings_utm.geometry.within(lake_buffer)]
        counts.append(len(nearby))

    lakes["building_count"] = counts

    # Classify: thresholds can be tuned
    def _classify(count: int) -> tuple[str, str]:
        if count <= 5:
            return ("low", "#2166ac")  # Blue - good for camping
        elif count <= 20:
            return ("medium", "#fdb863")  # Orange - moderate
        else:
            return ("high", "#b2182b")  # Red - many buildings

    classified = [_classify(c) for c in counts]
    lakes["density_class"] = [c[0] for c in classified]
    lakes["density_color"] = [c[1] for c in classified]

    return lakes


def process_lake_classification(
    gdb_paths: list[Path],
    bbox: BBox,
    lakes: gpd.GeoDataFrame,
    building_buffer_m: float = 500.0,
) -> gpd.GeoDataFrame:
    """Full pipeline: extract buildings and classify lakes."""
    print("Extracting buildings for lake classification...")
    buildings = extract_buildings(gdb_paths, bbox)
    print(f"  Found {len(buildings)} building features")

    if buildings.empty:
        print("  No buildings found, skipping density classification")
        lakes = lakes.copy()
        lakes["building_count"] = 0
        lakes["density_class"] = "low"
        lakes["density_color"] = "#2166ac"
        return lakes

    print(f"Classifying lakes by building density ({building_buffer_m}m buffer)...")
    classified = classify_lakes_by_density(lakes, buildings, building_buffer_m)

    for cls in ["low", "medium", "high"]:
        count = (classified["density_class"] == cls).sum()
        print(f"  {cls}: {count} lakes")

    return classified
