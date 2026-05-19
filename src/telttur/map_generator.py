"""Generate interactive HTML map using Folium."""

import json
from typing import Literal

import folium
import folium.plugins
import geopandas as gpd
import pandas as pd
from jinja2 import Template as _JinjaTemplate

from telttur.config import Config
from telttur.lakes import LakeCols
from telttur.landcover import get_wms_config
from telttur.maputils.interactivity import add_interactive_controls
from telttur.maputils.optimize import optimize_html
from telttur.scoring import (
    LEVEL_COLORS,
    LEVEL_NAMES,
    TentabilityLevel,
    get_scoring_detail_fields,
    get_scoring_score_fields,
)

# Sentinel value used in popup row lists to insert a visual separator.
_SEP = "__sep__"

# Reverse lookup: level name string ("Fair") → integer score (3).
# Used to encode score-level popup values as compact integers in the marker
# data array; the JavaScript factory function renders them as coloured badges.
_LEVEL_NAME_TO_INT: dict[str, int] = {name: level for level, name in LEVEL_NAMES.items()}


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
    fill_color = props.get(LakeCols.TENTABILITY_COLOR, "#67a9cf")
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


# ---------------------------------------------------------------------------
# Data-driven marker injection
# ---------------------------------------------------------------------------


class _JsBlock(folium.MacroElement):
    """Inject raw JavaScript into a parent element's script rendering context."""

    _template = _JinjaTemplate("{% macro script(this, kwargs) %}{{ this.js_code }}{% endmacro %}")

    def __init__(self, js_code: str) -> None:
        super().__init__()
        self._name = "js_block"
        self.js_code = js_code


# JS template for the marker factory.  Placeholders (__HEADERS__, __DATA__,
# __LAYER__) are replaced at build time.  Inline styles intentionally match
# the patterns that optimize.py's CSS-extraction step will shorten.
#
# Badge rendering: score-level values are stored as integers (1–5) in the data
# array.  The _bdg() helper converts them to coloured <span> badges at
# runtime, using the _ttL (level names) and _ttC (CSS class names) arrays.
# Non-integer values pass through as plain strings.
_MARKER_JS_TEMPLATE = """\
var _ttH=__HEADERS__;
var _ttD=__DATA__;
var _ttL=["","Terrible","Poor","Fair","Good","Excellent"];
var _ttC=["","tt-b1","tt-b2","tt-b3","tt-b4","tt-b5"];
(function(){
function _bdg(v){return typeof v==="number"&&v>=1&&v<=5?"<span class='"+_ttC[v]+"'>"+_ttL[v]+"</span>":""+v;}
function _am(d){
var lat=d[0],lng=d[1],fc=d[2],vals=d[3];
var m=L.circleMarker([lat,lng],{bubblingMouseEvents:true,color:"#333333",dashArray:null,dashOffset:null,fill:true,fillColor:fc,fillOpacity:0.65,fillRule:"evenodd",lineCap:"round",lineJoin:"round",opacity:1.0,radius:8,stroke:true,weight:0.8}).addTo(__LAYER__);
var h="<table style='font-size:12px;border-collapse:collapse'>";var vi=0;
for(var i=0;i<_ttH.length;i++){if(_ttH[i]===null){h+="<tr><td colspan='2'><hr style='margin:3px 0;border:none;border-top:1px solid #ccc'></td></tr>";continue;}h+="<tr><th style='text-align:left;padding:2px 6px 2px 0'>"+_ttH[i]+"</th><td style='padding:2px 0'>"+_bdg(vals[vi])+"</td></tr>";
vi++;}h+="</table>";var p=L.popup({maxWidth:300});
var e=$('<div style="width: 100.0%; height: 100.0%;">' + h + '</div>')[0];
p.setContent(e);
m.bindPopup(p);}
for(var i=0;i<_ttD.length;i++){_am(_ttD[i]);}
window._teltturLakesLayer=__LAYER__;
})();"""


def _build_marker_js(
    headers: list[str | None],
    marker_data: list[list[object]],
    layer_name: str,
) -> str:
    """Build JavaScript that creates circle markers from a compact data array."""
    headers_json = json.dumps(headers, ensure_ascii=False)
    data_json = json.dumps(marker_data, separators=(",", ":"), ensure_ascii=False)
    return (
        _MARKER_JS_TEMPLATE.replace("__HEADERS__", headers_json)
        .replace("__DATA__", data_json)
        .replace("__LAYER__", layer_name)
    )


def _add_lake_markers(
    m: folium.Map,
    lakes_clean: gpd.GeoDataFrame,
    use_cluster: bool = False,
    coord_precision: int = 6,
) -> None:
    """Add lakes as circle markers (one per lake centroid) to the map.

    Instead of creating individual Folium CircleMarker objects (which produces
    large, repetitive JavaScript), this injects a compact data-driven script:
    one factory function + one JSON data array.
    """
    rows = _lake_popup_rows(lakes_clean)
    if use_cluster:
        layer: folium.FeatureGroup | folium.plugins.MarkerCluster = folium.plugins.MarkerCluster(
            name="Lakes"
        )
    else:
        layer = folium.FeatureGroup(name="Lakes")

    # Build header list for popup template: alias strings, None for separators.
    headers: list[str | None] = []
    value_fields: list[str] = []
    for field, alias in rows:
        if field == _SEP:
            headers.append(None)
        else:
            headers.append(alias)
            value_fields.append(field)

    # Identify which value_fields are score-level columns (contain level names
    # like "Fair" that should be encoded as integers for JS badge rendering).
    score_level_cols: set[str] = set()
    if LakeCols.TENTABILITY_LEVEL in lakes_clean.columns:
        score_level_cols.add(LakeCols.TENTABILITY_LEVEL)
    for col, _ in get_scoring_score_fields(lakes_clean):
        score_level_cols.add(col)

    # Collect per-marker data.  Score-level values are stored as integers
    # (1–5) and rendered as coloured badges by the JS factory function.
    # All other values are plain strings.
    default_color = "#67a9cf"
    marker_data: list[list[object]] = []
    for _, row in lakes_clean.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        rep_point = geom.representative_point()
        lat = round(rep_point.y, coord_precision)
        lng = round(rep_point.x, coord_precision)
        color = row.get(LakeCols.TENTABILITY_COLOR, default_color) or default_color
        values: list[object] = []
        for f in value_fields:
            val = row.get(f, "")
            if f in score_level_cols:
                values.append(_LEVEL_NAME_TO_INT.get(str(val), 0) if val else 0)
            else:
                values.append(str(val) if val is not None else "")
        marker_data.append([lat, lng, color, values])

    if marker_data and rows:
        js = _build_marker_js(headers, marker_data, layer.get_name())
        _JsBlock(js).add_to(layer)

    layer.add_to(m)


def _lake_popup_rows(lakes: gpd.GeoDataFrame) -> list[tuple[str, str]]:
    """Return popup rows as (field, alias) pairs, with _SEP marking a visual separator.

    Order: Name → Tentability → per-dimension score badges → separator → Area → detail data.
    """
    rows: list[tuple[str, str]] = []

    # --- Score section ---
    for name_col, label in (("navn", "Name"), ("NAVN", "Name")):
        if name_col in lakes.columns:
            rows.append((name_col, label))
            break

    if LakeCols.TENTABILITY_LEVEL in lakes.columns:
        rows.append((LakeCols.TENTABILITY_LEVEL, "Tentability"))

    for col, alias in get_scoring_score_fields(lakes):
        rows.append((col, alias))

    # --- Detail section ---
    detail: list[tuple[str, str]] = []
    if LakeCols.AREA_DISPLAY in lakes.columns:
        detail.append((LakeCols.AREA_DISPLAY, "Area"))
    for col, alias in get_scoring_detail_fields(lakes):
        detail.append((col, alias))

    if detail:
        rows.append((_SEP, ""))
        rows.extend(detail)

    return rows


def _lake_popup_fields(lakes: gpd.GeoDataFrame) -> tuple[list[str], list[str]]:
    """Return (fields, aliases) for polygon-mode GeoJsonPopup (no separator)."""
    all_rows = [(f, a) for f, a in _lake_popup_rows(lakes) if f != _SEP]
    fields = [f for f, _ in all_rows]
    aliases = [a for _, a in all_rows]
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
    landcover_mode: Literal["wms", "vector", "disabled"] = "wms",
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

    base_map = config.map.base_map
    if base_map == "selectable":
        # Blank "None" option — lets users deselect all base tiles
        folium.TileLayer(
            tiles="",
            attr=" ",
            name="None",
            overlay=False,
            control=True,
        ).add_to(m)
        # Kartverket topographic
        folium.TileLayer(
            tiles=KARTVERKET_WMTS_URL,
            attr=KARTVERKET_ATTR,
            name="Kartverket Topografisk",
            overlay=False,
            control=True,
        ).add_to(m)
        if config.map.include_osm_layer:
            folium.TileLayer(
                tiles="OpenStreetMap",
                name="OpenStreetMap",
                overlay=False,
                control=True,
            ).add_to(m)
        # Greyscale added last = default active layer
        folium.TileLayer(
            tiles=KARTVERKET_WMTS_GRAY_URL,
            attr=KARTVERKET_ATTR,
            name="Kartverket Topografisk Grå",
            overlay=False,
            control=True,
        ).add_to(m)
    elif base_map == "topographic":
        folium.TileLayer(
            tiles=KARTVERKET_WMTS_URL,
            attr=KARTVERKET_ATTR,
            name="Kartverket Topografisk",
            overlay=False,
            control=False,
        ).add_to(m)
    else:  # greyscale (default)
        folium.TileLayer(
            tiles=KARTVERKET_WMTS_GRAY_URL,
            attr=KARTVERKET_ATTR,
            name="Kartverket Topografisk Grå",
            overlay=False,
            control=False,
        ).add_to(m)

    # Land cover layer
    overlay_count = 0

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
        overlay_count += 1
    elif landcover is not None and not landcover.empty:
        lc_geojson = json.loads(_prepare_for_json(landcover).to_json())
        folium.GeoJson(
            lc_geojson,
            name="Land cover (N50)",
            style_function=_style_landcover,
            show=False,
        ).add_to(m)
        overlay_count += 1

    # Roads layer (centerlines)
    if config.show_roads and not roads.empty:
        road_geojson = json.loads(_prepare_for_json(roads).to_json())
        folium.GeoJson(
            road_geojson,
            name="Roads",
            style_function=_style_road_line,
            show=False,
        ).add_to(m)
        overlay_count += 1

    # Lakes layer
    if not lakes.empty:
        lakes_clean = _prepare_for_json(lakes)
        if LakeCols.AREA_M2 in lakes_clean.columns:

            def _format_area(m2: float) -> str:
                if m2 >= 1_000_000:
                    return f"{m2 / 1_000_000:.2f} km²"
                elif m2 >= 10_000:
                    return f"{m2 / 10_000:.1f} ha"
                else:
                    return f"{m2:.0f} m²"

            lakes_clean[LakeCols.AREA_DISPLAY] = lakes_clean[LakeCols.AREA_M2].apply(_format_area)

        if config.lake_display_mode == "marker":
            _add_lake_markers(
                m,
                lakes_clean,
                use_cluster=config.map.use_marker_cluster,
                coord_precision=config.output.coordinate_precision,
            )
        else:
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
        overlay_count += 1

    # Layer control: show when base map is selectable, or when there are multiple overlays
    if config.map.base_map == "selectable" or overlay_count > 1:
        folium.LayerControl(collapsed=False).add_to(m)

    # Legend
    road_cats = []
    if config.show_roads and not roads.empty and "color" in roads.columns:
        seen: set[str] = set()
        for _, row in roads.iterrows():
            cat = row.get("category", "")
            if cat not in seen:
                seen.add(cat)
                road_cats.append({"color": row["color"], "label": row.get("label", "Road")})
    has_tentability = not lakes.empty and LakeCols.TENTABILITY_SCORE in lakes.columns
    _add_legend(m, road_cats, not lakes.empty, has_tentability=has_tentability)
    add_interactive_controls(m, config, lakes)

    return m


def save_map(m: folium.Map, config: Config) -> str:
    """Save the map to an HTML file. Returns the output path."""
    output_dir = config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / config.output_filename
    m.save(str(output_file))

    if config.output.minify:
        html = output_file.read_text(encoding="utf-8")
        optimized = optimize_html(html, config.output)
        output_file.write_text(optimized, encoding="utf-8")

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"  Output file size: {size_mb:.1f} MB")
    if size_mb > 50:
        print(
            f"  WARNING: Output file is {size_mb:.1f} MB (>50 MB). "
            "Consider increasing simplify_tolerance_m or switching landcover_mode to 'wms'."
        )

    return str(output_file)
