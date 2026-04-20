"""Generate interactive HTML map using Folium."""

import json

import folium
import geopandas as gpd
import pandas as pd

from telttur.config import Config
from telttur.landcover import get_wms_config
from telttur.scoring import LEVEL_COLORS, LEVEL_NAMES, TentabilityLevel

# Kartverket topographic map WMTS
KARTVERKET_WMTS_URL = (
    "https://cache.kartverket.no/v1/wmts/1.0.0/topo/default/webmercator/{z}/{y}/{x}.png"
)
KARTVERKET_WMTS_GRAY_URL = (
    "https://cache.kartverket.no/v1/wmts/1.0.0/topograatone/default/webmercator/{z}/{y}/{x}.png"
)
KARTVERKET_ATTR = '&copy; <a href="https://www.kartverket.no/">Kartverket</a>'


def _prepare_for_json(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert non-JSON-serializable columns (e.g. Timestamp) to strings."""
    gdf = gdf.copy()
    for col in gdf.columns:
        if col == "geometry":
            continue
        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].astype(str)
        elif gdf[col].dtype == object and not gdf[col].empty:
            if any(isinstance(v, pd.Timestamp) for v in gdf[col].dropna()):
                gdf[col] = gdf[col].astype(str)
    return gdf


def _style_road_line(feature: dict) -> dict:
    props = feature.get("properties", {})
    return {
        "color": props.get("color", "#999999"),
        "weight": 2,
        "opacity": 0.8,
    }


def _style_lake(feature: dict) -> dict:
    props = feature.get("properties", {})
    # Use tentability colour when available, otherwise neutral blue
    fill_color = props.get("tentability_color", "#67a9cf")
    return {
        "fillColor": fill_color,
        "color": "#333333",
        "weight": 0.8,
        "fillOpacity": 0.65,
    }


def _style_landcover(feature: dict) -> dict:
    props = feature.get("properties", {})
    return {
        "fillColor": props.get("color", "#CCCCCC"),
        "color": "#666666",
        "weight": 0.3,
        "fillOpacity": 0.3,
    }



def _lake_popup_fields(lakes: gpd.GeoDataFrame) -> tuple[list[str], list[str]]:
    """Return (fields, aliases) for a GeoJsonPopup showing the most useful lake columns."""
    fields: list[str] = []
    aliases: list[str] = []

    # Lake name
    for name_col, label in (("navn", "Name"), ("NAVN", "Name")):
        if name_col in lakes.columns:
            fields.append(name_col)
            aliases.append(label)
            break

    # Tentability columns (present only when scoring is enabled)
    tentability_cols = [
        ("tentability_level", "Tentability"),
        ("cabin_density_level", "Cabin density"),
        ("accessibility_level", "Accessibility"),
        ("building_count", "Cabins/homes within buffer"),
        ("road_distance_m", "Distance to road (m)"),
    ]
    for col, alias in tentability_cols:
        if col in lakes.columns:
            fields.append(col)
            aliases.append(alias)

    return fields, aliases


def _add_legend(
    m: folium.Map,
    road_categories: list[dict],
    has_lakes: bool,
    has_tentability: bool = False,
) -> None:
    """Add a HTML legend to the map."""
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
         background-color: white; padding: 10px; border: 2px solid grey;
         border-radius: 5px; font-size: 12px; max-width: 220px;">
    <b>Legend</b><br>
    <b>Roads:</b><br>
    """
    for cat in road_categories:
        legend_html += (
            f'<i style="background:{cat["color"]};width:12px;height:12px;'
            f'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
            f"{cat['label']}<br>"
        )

    if has_lakes:
        legend_html += "<b>Lakes &mdash; tentability:</b><br>"
        if has_tentability:
            for level in reversed(TentabilityLevel):  # Excellent first
                color = LEVEL_COLORS[int(level)]
                name = LEVEL_NAMES[int(level)]
                legend_html += (
                    f'<i style="background:{color};width:12px;height:12px;'
                    f'display:inline-block;margin-right:4px;opacity:0.7;"></i>'
                    f"{name}<br>"
                )
        else:
            legend_html += (
                '<i style="background:#67a9cf;width:12px;height:12px;'
                'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
                "(scoring disabled)<br>"
            )

    legend_html += "</div>"
    root = m.get_root()
    root.html.add_child(folium.Element(legend_html))  # folium typing limitation


def generate_map(
    config: Config,
    roads: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
    landcover: gpd.GeoDataFrame | None = None,
    landcover_mode: str = "wms",
) -> folium.Map:
    """Generate a Folium map with all layers."""
    # Center on bbox
    center_lat = (config.bbox.north + config.bbox.south) / 2
    center_lon = (config.bbox.east + config.bbox.west) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles=None,
    )

    # Base layer: blank "None" option — lets users deselect all base tiles
    folium.TileLayer(
        tiles="",
        attr=" ",
        name="None",
        overlay=False,
        control=True,
    ).add_to(m)

    # Base layer: Kartverket topographic
    folium.TileLayer(
        tiles=KARTVERKET_WMTS_URL,
        attr=KARTVERKET_ATTR,
        name="Kartverket Topografisk",
        overlay=False,
        control=True,
    ).add_to(m)

    # Base layer: Kartverket topographic gray
    folium.TileLayer(
        tiles=KARTVERKET_WMTS_GRAY_URL,
        attr=KARTVERKET_ATTR,
        name="Kartverket Topografisk Grå",
        overlay=False,
        control=True,
    ).add_to(m)

    # Also add OSM as fallback
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    # Land cover layer
    if landcover_mode == "wms":
        wms_config = get_wms_config()
        folium.WmsTileLayer(
            url=wms_config["url"],
            layers=wms_config["layers"],
            fmt=wms_config["fmt"],
            transparent=wms_config["transparent"],
            name=wms_config["name"],
            overlay=True,
            control=True,
            opacity=wms_config["opacity"],
        ).add_to(m)
    elif landcover is not None and not landcover.empty:
        lc_geojson = json.loads(_prepare_for_json(landcover).to_json())
        folium.GeoJson(
            lc_geojson,
            name="Land cover (N50)",
            style_function=_style_landcover,
            show=False,
        ).add_to(m)

    # Roads layer (centerlines)
    if not roads.empty:
        road_geojson = json.loads(_prepare_for_json(roads).to_json())
        folium.GeoJson(
            road_geojson,
            name="Roads",
            style_function=_style_road_line,
        ).add_to(m)

    # Lakes layer
    if not lakes.empty:
        lakes_clean = _prepare_for_json(lakes)
        lake_geojson = json.loads(lakes_clean.to_json())
        lake_layer = folium.GeoJson(
            lake_geojson,
            name="Lakes",
            style_function=_style_lake,
        )
        # Build popup showing only the informative columns
        popup_fields, popup_aliases = _lake_popup_fields(lakes_clean)
        if popup_fields:
            folium.GeoJsonPopup(
                fields=popup_fields,
                aliases=popup_aliases,
                localize=True,
            ).add_to(lake_layer)
        lake_layer.add_to(m)

    # Layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Legend
    road_cats = []
    if not roads.empty and "color" in roads.columns:
        seen: set[str] = set()
        for _, row in roads.iterrows():
            cat = row.get("category", "")
            if cat not in seen:
                seen.add(cat)
                road_cats.append({"color": row["color"], "label": row.get("label", "Road")})
    has_tentability = not lakes.empty and "tentability_score" in lakes.columns
    _add_legend(m, road_cats, not lakes.empty, has_tentability=has_tentability)

    return m


def save_map(m: folium.Map, config: Config) -> str:
    """Save the map to an HTML file. Returns the output path."""
    output_dir = config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / config.output_filename
    m.save(str(output_file))

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"  Output file size: {size_mb:.1f} MB")
    if size_mb > 50:
        print(
            f"  WARNING: Output file is {size_mb:.1f} MB (>50 MB). "
            "Consider increasing simplify_tolerance_m or switching landcover_mode to 'wms'."
        )

    return str(output_file)
