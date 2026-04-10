"""Road extraction and buffering from N50 Kartdata."""

from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox

# N50 uses UTM33 (EPSG:25833)
CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"

# Road category styling — vegkategori single-letter codes and typeveg values from N50
ROAD_CATEGORIES: dict[str, dict] = {
    # vegkategori values (single uppercase letter)
    "E": {"label": "Europavei", "color": "#d73027"},
    "R": {"label": "Riksvei", "color": "#fc8d59"},
    "F": {"label": "Fylkesvei", "color": "#fee08b"},
    "K": {"label": "Kommunalvei", "color": "#d9ef8b"},
    "P": {"label": "Privat vei", "color": "#91cf60"},
    "S": {"label": "Skogsvei", "color": "#1a9850"},
    # typeveg values (for roads without vegkategori)
    "enkelBilveg": {"label": "Bilveg", "color": "#bababa"},
    "traktorveg": {"label": "Traktorveg", "color": "#4575b4"},
    "gangOgSykkelveg": {"label": "Gang- og sykkelvei", "color": "#74add1"},
    "sti": {"label": "Sti / turvei", "color": "#e0f3f8"},
}

# typeveg values that represent water routes — skip buffering on land
_FERRY_TYPEVEG = {"passasjerferje", "bilferje"}


def find_road_layers(gdb_path: Path) -> list[str]:
    """List layers in a .gdb that likely contain road data."""
    all_layers = fiona.listlayers(str(gdb_path))
    road_keywords = ["veg", "samferds", "road"]
    matches = [
        layer
        for layer in all_layers
        if any(kw in layer.lower() for kw in road_keywords) and "senterlinje" in layer.lower()
    ]
    if not matches:
        print(f"  Available layers in {gdb_path.name}: {all_layers}")
    return matches


def _bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    """Convert WGS84 bbox to UTM33 bounds (minx, miny, maxx, maxy)."""
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    bbox_utm = bbox_gdf.to_crs(CRS_UTM33)
    b = bbox_utm.total_bounds  # minx, miny, maxx, maxy
    return (b[0], b[1], b[2], b[3])


def extract_roads(
    gdb_paths: list[Path],
    bbox: BBox,
) -> gpd.GeoDataFrame:
    """Extract road centerlines from N50 FGDB files, clipped to bbox."""
    frames: list[gpd.GeoDataFrame] = []

    for gdb_path in gdb_paths:
        road_layers = find_road_layers(gdb_path)
        if not road_layers:
            print(f"  No road layers found in {gdb_path.name}")
            continue

        for layer_name in road_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name)

            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif str(gdf.crs) != CRS_UTM33:
                gdf = gdf.to_crs(CRS_UTM33)

            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry"], crs=CRS_UTM33)

    roads = gpd.pd.concat(frames, ignore_index=True)
    roads = gpd.GeoDataFrame(roads, crs=CRS_UTM33)

    # Clip to bbox
    utm_bounds = _bbox_to_utm33(bbox)
    clip_box = box(*utm_bounds)
    roads = roads.clip(clip_box)

    # Keep only linestring geometries
    roads = roads[roads.geometry.geom_type.isin(["LineString", "MultiLineString"])]

    return roads


def buffer_roads(
    roads: gpd.GeoDataFrame,
    buffer_distance_m: float,
    simplify_tolerance_m: float = 0,
) -> gpd.GeoDataFrame:
    """Buffer road centerlines and dissolve by category.

    Returns a GeoDataFrame with one row per road category,
    with columns: category, label, color, geometry (polygon).
    """
    if roads.empty:
        return gpd.GeoDataFrame(
            columns=["category", "label", "color", "geometry"],
            crs=CRS_WGS84,
        )

    roads = roads.copy()

    # Filter out railways (Bane) — they are not roads
    if "objtype" in roads.columns:
        roads = roads[roads["objtype"] != "Bane"]

    # Filter out ferry routes — water crossings, not land roads
    if "typeveg" in roads.columns:
        roads = roads[~roads["typeveg"].isin(_FERRY_TYPEVEG)]

    if roads.empty:
        return gpd.GeoDataFrame(
            columns=["category", "label", "color", "geometry"],
            crs=CRS_WGS84,
        )

    # Assign a unified category: vegkategori where set, otherwise typeveg
    if "vegkategori" in roads.columns and "typeveg" in roads.columns:
        roads["_category"] = roads["vegkategori"].where(
            roads["vegkategori"].notna(), roads["typeveg"]
        )
    elif "vegkategori" in roads.columns:
        roads["_category"] = roads["vegkategori"].fillna("other")
    elif "typeveg" in roads.columns:
        roads["_category"] = roads["typeveg"].fillna("other")
    else:
        roads["_category"] = "other"

    results = []
    for cat_value, group in roads.groupby("_category", dropna=False):
        cat_key = str(cat_value).strip() if cat_value and str(cat_value) != "nan" else "other"
        style = ROAD_CATEGORIES.get(cat_key, {"label": cat_key, "color": "#999999"})

        buffered = group.geometry.buffer(buffer_distance_m)

        if simplify_tolerance_m > 0:
            buffered = buffered.simplify(simplify_tolerance_m)

        dissolved = buffered.union_all()

        results.append(
            {
                "category": cat_key,
                "label": style["label"],
                "color": style["color"],
                "geometry": dissolved,
            }
        )

    result_gdf = gpd.GeoDataFrame(results, crs=CRS_UTM33)
    return result_gdf.to_crs(CRS_WGS84)


def process_roads(
    gdb_paths: list[Path],
    bbox: BBox,
    buffer_distance_m: float,
    simplify_tolerance_m: float = 0,
) -> gpd.GeoDataFrame:
    """Full pipeline: extract roads, buffer, return in WGS84."""
    print("Extracting roads...")
    roads = extract_roads(gdb_paths, bbox)
    print(f"  Found {len(roads)} road features")

    print(f"Buffering roads ({buffer_distance_m}m)...")
    buffered = buffer_roads(roads, buffer_distance_m, simplify_tolerance_m)
    print(f"  Created {len(buffered)} road buffer polygon(s)")

    return buffered
