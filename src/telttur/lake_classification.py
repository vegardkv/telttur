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


# Norwegian building type codes (bygningstype) that indicate habitation:
# 100-199: Residential buildings (boligbygninger), including:
#   161-169: Cabins/fritidsboliger (hytte) - the dominant type in mountain areas
#   111-119: Single-family homes, 121-129: Two-family homes, etc.
RESIDENTIAL_BYGNINGSTYPE_MIN = 100
RESIDENTIAL_BYGNINGSTYPE_MAX = 199


def extract_buildings(
    gdb_paths: list[Path],
    bbox: BBox,
) -> gpd.GeoDataFrame:
    """Extract residential/cabin building points from N50 FGDB files, clipped to bbox.

    Filters to objtype=='Bygning' and bygningstype in 100-199 (residential/cabins).
    This excludes masts, tanks, industrial buildings etc. that are not relevant
    for estimating cabin/habitation density around lakes.
    """
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = _bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        building_layers = find_building_layers(gdb_path)
        if not building_layers:
            continue

        for layer_name in building_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name, bbox=utm_bounds)

            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif str(gdf.crs) != CRS_UTM33:
                gdf = gdf.to_crs(CRS_UTM33)

            # Filter to actual buildings (exclude masts, tanks, parking areas, etc.)
            if "objtype" in gdf.columns:
                gdf = gdf[gdf["objtype"] == "Bygning"]

            # Filter to residential/cabin types (100-199) to exclude barns,
            # industrial buildings, churches, etc.
            if "bygningstype" in gdf.columns:
                gdf = gdf[
                    gdf["bygningstype"].between(
                        RESIDENTIAL_BYGNINGSTYPE_MIN, RESIDENTIAL_BYGNINGSTYPE_MAX
                    )
                ]

            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry"], crs=CRS_UTM33)

    buildings = gpd.pd.concat(frames, ignore_index=True)
    buildings = gpd.GeoDataFrame(buildings, crs=CRS_UTM33)

    # Clip to exact bbox (bbox= pre-filters by bounding box only)
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
    lakes_utm = lakes.to_crs(CRS_UTM33).copy()
    buildings_utm = buildings.to_crs(CRS_UTM33) if buildings.crs != CRS_UTM33 else buildings.copy()

    # Vectorized spatial join: buffer all lake polygons once, then sjoin
    lakes_utm["_buffered"] = lakes_utm.geometry.buffer(buffer_m)
    lake_buffers = lakes_utm[["_buffered"]].set_geometry("_buffered").rename_geometry("geometry")
    lake_buffers.index = lakes_utm.index

    joined = gpd.sjoin(
        lake_buffers,
        buildings_utm[["geometry"]],
        how="left",
        predicate="contains",
    )
    counts = joined.groupby(joined.index).size()
    # sjoin drops rows with no match for inner; left join gives NaN for index_right
    building_count = joined.groupby(joined.index)["index_right"].count()
    lakes["building_count"] = lakes.index.map(building_count).fillna(0).astype(int)

    # Classify by residential/cabin density within buffer.
    # Thresholds tuned on Innlandet (N50) data: most lakes are remote (54% have
    # 0 buildings within 500m, 79% have ≤5). Distribution:
    #   low  (≤5 buildings):  ~79% of lakes — good for wild camping
    #   medium (6-20):        ~12% of lakes — some cabin development
    #   high  (>20):          ~10% of lakes — busy cabin/residential area
    def _classify(count: int) -> tuple[str, str]:
        if count <= 5:
            return ("low", "#2166ac")  # Blue - good for camping
        elif count <= 20:
            return ("medium", "#fdb863")  # Orange - moderate development
        else:
            return ("high", "#b2182b")  # Red - busy cabin area

    classified = [_classify(int(c)) for c in lakes["building_count"]]
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
