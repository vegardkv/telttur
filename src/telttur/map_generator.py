"""Generate interactive HTML map using Folium."""

import json

import folium
import geopandas as gpd
import pandas as pd

from telttur.config import Config
from telttur.landcover import get_wms_config

# Kartverket topographic map WMTS
KARTVERKET_WMTS_URL = (
    "https://cache.kartverket.no/v1/wmts/1.0.0/topo/default/webmercator/{z}/{y}/{x}.png"
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
    return gdf


def _style_road_buffer(feature: dict) -> dict:
    props = feature.get("properties", {})
    return {
        "fillColor": props.get("color", "#999999"),
        "color": props.get("color", "#999999"),
        "weight": 1,
        "fillOpacity": 0.25,
    }


def _style_lake(feature: dict) -> dict:
    props = feature.get("properties", {})
    reachable = props.get("reachable", False)
    # If density classification is available, use that color
    if "density_color" in props:
        fill_color = props["density_color"]
    elif reachable:
        fill_color = "#2166ac"  # Blue for reachable
    else:
        fill_color = "#67a9cf"  # Lighter blue for unreachable

    return {
        "fillColor": fill_color,
        "color": "#08519c",
        "weight": 1,
        "fillOpacity": 0.6,
    }


def _style_landcover(feature: dict) -> dict:
    props = feature.get("properties", {})
    return {
        "fillColor": props.get("color", "#CCCCCC"),
        "color": "#666666",
        "weight": 0.3,
        "fillOpacity": 0.3,
    }


def _lake_popup(feature: dict) -> folium.Popup | None:
    props = feature.get("properties", {})
    parts = []
    if "navn" in props and props["navn"]:
        parts.append(f"<b>{props['navn']}</b>")
    elif "NAVN" in props and props["NAVN"]:
        parts.append(f"<b>{props['NAVN']}</b>")
    if "reachable" in props:
        status = "Yes" if props["reachable"] else "No"
        parts.append(f"Reachable from road: {status}")
    if "density_class" in props:
        label = {"low": "Low (good for camping)", "medium": "Medium", "high": "High (busy)"}.get(
            props["density_class"], props["density_class"]
        )
        parts.append(f"Cabin density: {label}")
    if "building_count" in props:
        parts.append(f"Cabins/homes nearby: {props['building_count']}")
    if parts:
        return folium.Popup("<br>".join(parts), max_width=300)
    return None


def _add_legend(
    m: folium.Map,
    road_categories: list[dict],
    has_lakes: bool,
    has_density: bool = False,
) -> None:
    """Add a simple HTML legend to the map."""
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
         background-color: white; padding: 10px; border: 2px solid grey;
         border-radius: 5px; font-size: 12px; max-width: 220px;">
    <b>Legend</b><br>
    <b>Road buffer:</b><br>
    """
    for cat in road_categories:
        legend_html += (
            f'<i style="background:{cat["color"]};width:12px;height:12px;'
            f'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
            f"{cat['label']}<br>"
        )

    if has_lakes:
        legend_html += "<b>Lakes:</b><br>"
        if has_density:
            legend_html += (
                '<i style="background:#2166ac;width:12px;height:12px;'
                'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
                "Few cabins nearby (&le;5)<br>"
            )
            legend_html += (
                '<i style="background:#fdb863;width:12px;height:12px;'
                'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
                "Some cabins (6&ndash;20)<br>"
            )
            legend_html += (
                '<i style="background:#b2182b;width:12px;height:12px;'
                'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
                "Many cabins (&gt;20)<br>"
            )
        else:
            legend_html += (
                '<i style="background:#2166ac;width:12px;height:12px;'
                'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
                "Reachable<br>"
            )
            legend_html += (
                '<i style="background:#67a9cf;width:12px;height:12px;'
                'display:inline-block;margin-right:4px;opacity:0.6;"></i>'
                "Not reachable<br>"
            )

    legend_html += "</div>"
    root = m.get_root()
    root.html.add_child(folium.Element(legend_html))  # folium typing limitation


def generate_map(
    config: Config,
    road_buffers: gpd.GeoDataFrame,
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

    # Base layer: Kartverket topographic
    folium.TileLayer(
        tiles=KARTVERKET_WMTS_URL,
        attr=KARTVERKET_ATTR,
        name="Kartverket Topografisk",
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

    # Road buffers layer
    if not road_buffers.empty:
        road_geojson = json.loads(_prepare_for_json(road_buffers).to_json())
        folium.GeoJson(
            road_geojson,
            name=f"Road buffer ({config.buffer_distance_m:.0f}m)",
            style_function=_style_road_buffer,
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
        # Add popups for lakes
        folium.GeoJsonPopup(
            fields=[c for c in lakes_clean.columns if c != "geometry"],
            aliases=[c for c in lakes_clean.columns if c != "geometry"],
            localize=True,
        ).add_to(lake_layer)
        lake_layer.add_to(m)

    # Layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Legend
    road_cats = []
    if not road_buffers.empty and "color" in road_buffers.columns:
        for _, row in road_buffers.iterrows():
            road_cats.append({"color": row["color"], "label": row.get("label", "Road")})
    has_density = not lakes.empty and "density_class" in lakes.columns
    _add_legend(m, road_cats, not lakes.empty, has_density=has_density)

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
