"""Land cover visualization (WMS overlay or N50 vector)."""

from pathlib import Path

import fiona
import geopandas as gpd
from shapely.geometry import box

from telttur.config import BBox

CRS_UTM33 = "EPSG:25833"
CRS_WGS84 = "EPSG:4326"

# FKB-AR5 WMS endpoint (open, no authentication required)
AR5_WMS_URL = "https://wms.nibio.no/cgi-bin/ar5"
AR5_WMS_LAYERS = "Arealtype"
AR5_WMS_FORMAT = "image/png"

# Land cover type colors (N50 markslag / arealdekke)
LANDCOVER_COLORS: dict[str, str] = {
    "skog": "#228B22",
    "myr": "#8B6914",
    "åpen fastmark": "#DEB887",
    "bebygd": "#DC143C",
    "samferdsel": "#808080",
    "dyrka mark": "#FFD700",
    "ferskvann": "#4169E1",
    "snøisbre": "#F0F8FF",
    "hav": "#000080",
}


def get_wms_config() -> dict:
    """Return configuration dict for adding AR5 WMS as a Folium tile layer."""
    return {
        "url": AR5_WMS_URL,
        "layers": AR5_WMS_LAYERS,
        "fmt": AR5_WMS_FORMAT,
        "name": "Arealressurskart (AR5)",
        "transparent": True,
        "opacity": 0.5,
    }


def find_landcover_layers(gdb_path: Path) -> list[str]:
    """List layers that contain land cover / arealdekke data."""
    all_layers = fiona.listlayers(str(gdb_path))
    keywords = ["arealdekke", "arealbruk", "markslag", "landcover"]
    return [
        layer
        for layer in all_layers
        if any(kw in layer.lower() for kw in keywords) and "omrade" in layer.lower()  # noqa: PLR2004
    ]


def _bbox_to_utm33(bbox: BBox) -> tuple[float, float, float, float]:
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(bbox.west, bbox.south, bbox.east, bbox.north)],
        crs=CRS_WGS84,
    )
    bbox_utm = bbox_gdf.to_crs(CRS_UTM33)
    b = bbox_utm.total_bounds
    return (b[0], b[1], b[2], b[3])


def extract_landcover(
    gdb_paths: list[Path],
    bbox: BBox,
    simplify_tolerance_m: float = 0,
) -> gpd.GeoDataFrame:
    """Extract land cover polygons from N50, clipped to bbox."""
    frames: list[gpd.GeoDataFrame] = []
    utm_bounds = _bbox_to_utm33(bbox)

    for gdb_path in gdb_paths:
        lc_layers = find_landcover_layers(gdb_path)
        if not lc_layers:
            print(f"  No land cover layers in {gdb_path.name}")
            continue

        for layer_name in lc_layers:
            print(f"  Reading {layer_name} from {gdb_path.name}...")
            gdf = gpd.read_file(str(gdb_path), layer=layer_name, bbox=utm_bounds)

            if gdf.crs is None:
                gdf = gdf.set_crs(CRS_UTM33)
            elif str(gdf.crs) != CRS_UTM33:
                gdf = gdf.to_crs(CRS_UTM33)

            # Keep only polygon features
            gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

            # Exclude water features (handled by lakes layer)
            type_col = None
            for candidate in ["objtype", "OBJTYPE", "objType"]:
                if candidate in gdf.columns:
                    type_col = candidate
                    break

            if type_col:
                water_types = ["innsjø", "innsjo", "hav", "elv", "ferskvann"]
                mask = ~gdf[type_col].str.lower().isin(water_types)
                gdf = gdf[mask]

            frames.append(gdf)

    if not frames:
        return gpd.GeoDataFrame(columns=["geometry"], crs=CRS_WGS84)

    landcover = gpd.pd.concat(frames, ignore_index=True)
    landcover = gpd.GeoDataFrame(landcover, crs=CRS_UTM33)

    # Clip to bbox (exact clip after bbox pre-filter)
    clip_box = box(*utm_bounds)
    landcover = landcover.clip(clip_box)

    if simplify_tolerance_m > 0:
        landcover["geometry"] = landcover.geometry.simplify(simplify_tolerance_m)

    return landcover.to_crs(CRS_WGS84)


def assign_landcover_colors(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add a 'color' column based on the object type."""
    gdf = gdf.copy()

    type_col = None
    for candidate in ["objtype", "OBJTYPE", "objType"]:
        if candidate in gdf.columns:
            type_col = candidate
            break

    if type_col is None:
        gdf["color"] = "#CCCCCC"
        return gdf

    def _get_color(obj_type: str) -> str:
        obj_lower = str(obj_type).lower()
        for key, color in LANDCOVER_COLORS.items():
            if key in obj_lower:
                return color
        return "#CCCCCC"

    gdf["color"] = gdf[type_col].apply(_get_color)
    return gdf


def process_landcover(
    gdb_paths: list[Path],
    bbox: BBox,
    simplify_tolerance_m: float = 0,
) -> gpd.GeoDataFrame:
    """Full pipeline: extract and color-code land cover polygons."""
    print("Extracting land cover...")
    lc = extract_landcover(gdb_paths, bbox, simplify_tolerance_m)
    print(f"  Found {len(lc)} land cover features")

    lc = assign_landcover_colors(lc)
    return lc
