"""Lake extraction from N50 Kartdata."""

from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox

CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"


def find_lake_layers(gdb_path: Path) -> list[str]:
    """List layers in a .gdb that likely contain lake/water data."""
    all_layers = fiona.listlayers(str(gdb_path))
    water_keywords = ["innsj", "vann", "water", "arealdekke", "Innsj", "Vann"]
    matches = [
        layer for layer in all_layers if any(kw.lower() in layer.lower() for kw in water_keywords)
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

    for gdb_path in gdb_paths:
        lake_layers = find_lake_layers(gdb_path)
        if not lake_layers:
            print(f"  No lake/water layers found in {gdb_path.name}")
            continue

        for layer_name in lake_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name)

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

    # Clip to bbox
    utm_bounds = _bbox_to_utm33(bbox)
    clip_box = box(*utm_bounds)
    lakes = lakes.clip(clip_box)

    if simplify_tolerance_m > 0:
        lakes["geometry"] = lakes.geometry.simplify(simplify_tolerance_m)

    return lakes.to_crs(CRS_WGS84)


def classify_lake_reachability(
    lakes: gpd.GeoDataFrame,
    road_buffers: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Add a 'reachable' column: True if the lake intersects any road buffer."""
    if lakes.empty or road_buffers.empty:
        lakes = lakes.copy()
        lakes["reachable"] = False
        return lakes

    # Ensure same CRS
    if lakes.crs != road_buffers.crs:
        road_buffers = road_buffers.to_crs(lakes.crs)

    # Union all road buffers into one geometry
    all_buffers = road_buffers.union_all()

    lakes = lakes.copy()
    lakes["reachable"] = lakes.geometry.intersects(all_buffers)

    return lakes


def process_lakes(
    gdb_paths: list[Path],
    bbox: BBox,
    simplify_tolerance_m: float = 0,
    road_buffers: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Full pipeline: extract lakes, optionally classify reachability."""
    print("Extracting lakes...")
    lakes = extract_lakes(gdb_paths, bbox, simplify_tolerance_m)
    print(f"  Found {len(lakes)} lake features")

    if road_buffers is not None and not road_buffers.empty:
        print("Classifying lake reachability...")
        lakes = classify_lake_reachability(lakes, road_buffers)
        reachable_count = lakes["reachable"].sum()
        print(f"  {reachable_count}/{len(lakes)} lakes are reachable from roads")

    return lakes
