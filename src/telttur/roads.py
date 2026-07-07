"""Road extraction and buffering from N50 Kartdata."""

from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox
from telttur.geo import CRS_UTM33, CRS_WGS84, bbox_to_utm33, read_n50_layer

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
    # Non-motorised routes: excluded from buffering by default via config
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


def extract_roads(
    gdb_paths: list[Path],
    bbox: BBox,
) -> gpd.GeoDataFrame:
    """Extract road centerlines from N50 FGDB files, clipped to bbox."""
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        road_layers = find_road_layers(gdb_path)
        if not road_layers:
            print(f"  No road layers found in {gdb_path.name}")
            continue

        for layer_name in road_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            frames.append(read_n50_layer(gdb_path, layer_name, utm_bounds))

    if not frames:
        # Category 1: N50 always ships a road centerline layer, so finding none means the
        # download is incomplete/corrupt (not that the region lacks roads).
        names = ", ".join(p.name for p in gdb_paths)
        raise RuntimeError(
            f"No road centerline layer found in N50 data ({names}); the N50 download "
            "may be incomplete. Delete the cache and re-run."
        )

    roads = gpd.pd.concat(frames, ignore_index=True)
    roads = gpd.GeoDataFrame(roads, crs=CRS_UTM33)

    # Clip to bbox (exact clip after bbox pre-filter)
    clip_box = box(*utm_bounds)
    roads = roads.clip(clip_box)

    # Keep only linestring geometries
    roads = roads[roads.geometry.geom_type.isin(["LineString", "MultiLineString"])]

    return roads


def _style_roads(roads: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign category/label/color to road centerlines for map display.

    Returns a GeoDataFrame with columns: category, label, color, geometry (lines).
    """
    # Category 3: an empty frame here is a genuinely road-free region, not an error.
    if roads.empty:
        return gpd.GeoDataFrame(
            columns=["category", "label", "color", "geometry"],
            crs=CRS_WGS84,
        )

    roads = roads.copy()

    # Filter out railways (Bane)
    if "objtype" in roads.columns:
        roads = roads[roads["objtype"] != "Bane"]

    # Filter out ferry routes
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

    roads["category"] = roads["_category"].apply(
        lambda v: str(v).strip() if v and str(v) != "nan" else "other"
    )
    roads["label"] = roads["category"].apply(
        lambda k: ROAD_CATEGORIES.get(k, {"label": k, "color": "#999999"})["label"]
    )
    roads["color"] = roads["category"].apply(
        lambda k: ROAD_CATEGORIES.get(k, {"label": k, "color": "#999999"})["color"]
    )

    result = roads[["category", "label", "color", "geometry"]].copy()
    return result.to_crs(CRS_WGS84)


def process_roads(
    gdb_paths: list[Path],
    bbox: BBox,
) -> gpd.GeoDataFrame:
    """Full pipeline: extract and style road centerlines for map display."""
    print("Extracting roads...")
    roads = extract_roads(gdb_paths, bbox)
    print(f"  Found {len(roads)} road features")

    print("Styling roads for display...")
    styled_lines = _style_roads(roads)
    print(f"  Styled {len(styled_lines)} road features")

    return styled_lines
