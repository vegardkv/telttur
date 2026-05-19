"""Interactive scoring controls panel injected into the Folium map."""

from __future__ import annotations

import json

import folium
import geopandas as gpd

from telttur.config import (
    Config,
    InteractiveAccessibilityRange,
    InteractiveAr5Buffers,
    InteractiveCabinDensitySlider,
    InteractiveDimensionToggles,
    ScoringConfig,
)
from telttur.lakes import LakeCols


def add_interactive_controls(
    m: folium.Map,
    config: Config,
    lakes: gpd.GeoDataFrame,
) -> None:
    """Inject a floating interactive scoring control panel into a Folium map.

    The panel renders checkboxes and sliders based on
    ``config.map.interactive_controls`` and updates lake marker colours in
    real time without requiring a server.
    """
    controls = config.map.interactive_controls
    if not controls.enabled:
        return
    if not config.scoring.enabled:
        return
    if lakes.empty or LakeCols.TENTABILITY_SCORE not in lakes.columns:
        return

    scoring = config.scoring
    dt = controls.dimension_toggles

    # Guard: only show interactive sliders when the underlying data columns are present.
    ar: InteractiveAccessibilityRange | None = controls.accessibility_range
    if LakeCols.ROAD_DISTANCE_M not in lakes.columns:
        ar = None

    cabin_density_slider: InteractiveCabinDensitySlider | None = controls.cabin_density_slider
    if LakeCols.BUILDING_DENSITY not in lakes.columns:
        cabin_density_slider = None

    ar5_buffers: InteractiveAr5Buffers | None = controls.ar5_buffers
    if (
        LakeCols.INDUSTRIAL_DISTANCE_M not in lakes.columns
        or LakeCols.RESIDENTIAL_DISTANCE_M not in lakes.columns
    ):
        ar5_buffers = None

    lake_data_block = _build_lake_data_block(
        lakes,
        config.lake_display_mode == "marker",
    )

    panel_html = _build_panel_html(
        dt=dt,
        scoring=scoring,
        show_min_area=controls.min_lake_area,
        min_area_init=int(config.min_lake_area_m2),
        access_range=ar,
        cabin_density_slider=cabin_density_slider,
        ar5_buffers=ar5_buffers,
    )

    js = _build_js(
        lake_data_block=lake_data_block,
        dt=dt,
        scoring=scoring,
        show_min_area=controls.min_lake_area,
        min_area_init=int(config.min_lake_area_m2),
        access_range=ar,
        cabin_density_slider=cabin_density_slider,
        ar5_buffers=ar5_buffers,
    )

    root = m.get_root()
    root.html.add_child(folium.Element(panel_html + "\n" + js))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_lake_data_block(
    lakes: gpd.GeoDataFrame,
    is_marker_mode: bool,
) -> str:
    """Return a JS variable declaration with per-lake data keyed by 'lat,lng'."""
    if not is_marker_mode:
        return ""

    lake_lookup: dict[str, dict] = {}
    for _, row in lakes.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        rep_point = geom.representative_point()
        key = f"{round(rep_point.y, 6):.6f},{round(rep_point.x, 6):.6f}"

        def _float(col: str, default: float = 0.0) -> float:
            v = row.get(col)
            try:
                return float(v) if v is not None else default
            except (TypeError, ValueError):
                return default

        def _int(col: str, default: int = 3) -> int:
            v = row.get(col)
            try:
                return int(v) if v is not None else default
            except (TypeError, ValueError):
                return default

        lake_lookup[key] = {
            LakeCols.AREA_M2: _float(LakeCols.AREA_M2),
            LakeCols.CABIN_DENSITY_SCORE: _int(LakeCols.CABIN_DENSITY_SCORE),
            LakeCols.ACCESSIBILITY_SCORE: _int(LakeCols.ACCESSIBILITY_SCORE),
            LakeCols.AR5_LAND_USE_SCORE: _int(LakeCols.AR5_LAND_USE_SCORE),
            LakeCols.FISHING_SCORE: _int(LakeCols.FISHING_SCORE),
            LakeCols.ROAD_DISTANCE_M: _float(LakeCols.ROAD_DISTANCE_M),
            LakeCols.BUILDING_DENSITY: _float(LakeCols.BUILDING_DENSITY),
            LakeCols.INDUSTRIAL_DISTANCE_M: _float(LakeCols.INDUSTRIAL_DISTANCE_M),
            LakeCols.RESIDENTIAL_DISTANCE_M: _float(LakeCols.RESIDENTIAL_DISTANCE_M),
        }

    return f"var TELTTUR_LAKE_DATA = {json.dumps(lake_lookup)};\n"


def _build_panel_html(
    *,
    dt: InteractiveDimensionToggles,
    scoring: ScoringConfig,
    show_min_area: bool,
    min_area_init: int,
    access_range: InteractiveAccessibilityRange | None,
    cabin_density_slider: InteractiveCabinDensitySlider | None,
    ar5_buffers: InteractiveAr5Buffers | None,
) -> str:
    parts: list[str] = [
        '<div id="telttur-controls" style="'
        "position:fixed;top:80px;right:10px;z-index:9999;"
        "background:white;padding:10px 14px;border:2px solid #666;"
        "border-radius:6px;font-size:13px;min-width:190px;max-width:250px;"
        'box-shadow:2px 2px 8px rgba(0,0,0,.25);font-family:sans-serif;">',
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'margin-bottom:6px;">'
        '<b style="font-size:14px">\u2699 Scoring</b>'
        "<button onclick=\"var b=document.getElementById('telttur-body'),"
        "s=b.style;s.display=s.display==='none'?'block':'none'"
        '" style="background:none;border:none;cursor:pointer;font-size:13px;padding:0"'
        ">\u25bc</button></div>",
        '<div id="telttur-body">',
    ]

    # Dimension toggle checkboxes \u2014 each entry reads directly from the models.
    _dim_defs = [
        (dt.cabin_density, scoring.cabin_density.enabled, "telttur-cabin", "Cabin density"),
        (dt.accessibility, scoring.accessibility.enabled, "telttur-access", "Accessibility"),
        (dt.ar5_land_use, scoring.ar5_land_use.enabled, "telttur-ar5", "Land use (AR5)"),
        (dt.fishing, scoring.fishing.enabled, "telttur-fishing", "Fishing"),
    ]
    visible_dims = [(init, el_id, label) for show, init, el_id, label in _dim_defs if show]
    if visible_dims:
        parts.append("<b>Dimensions:</b><br>")
        for init, el_id, label in visible_dims:
            chk = "checked" if init else ""
            parts.append(
                f'<label><input type="checkbox" id="{el_id}" {chk} '
                f'onchange="teltturUpdate()"> {label}</label><br>'
            )
        parts.append('<div style="height:6px"></div>')

    if show_min_area:
        parts.append(
            "<b>Min lake area:</b> "
            f'<span id="telttur-min-area-val" style="font-weight:bold">{min_area_init}</span> m\u00b2<br>'
            f'<input type="range" id="telttur-min-area" min="0" max="100000" '
            f'step="500" value="{min_area_init}" style="width:100%;margin:3px 0 8px"'
            " oninput=\"document.getElementById('telttur-min-area-val').textContent="
            'this.value;teltturUpdate()">'
        )

    if access_range is not None and access_range.enabled:
        min_val = int(access_range.min_m)
        max_val = int(access_range.max_m)
        slider_max = int(access_range.slider_max_m)
        parts.append(
            "<b>Accessibility distance:</b><br>"
            f'Min: <span id="telttur-ar-min-val" style="font-weight:bold">{min_val}</span> m<br>'
            f'<input type="range" id="telttur-ar-min" min="0" max="{slider_max}" '
            f'step="100" value="{min_val}" style="width:100%;margin:2px 0 6px"'
            " oninput=\"document.getElementById('telttur-ar-min-val').textContent="
            'this.value;teltturUpdate()"><br>'
            f'Max: <span id="telttur-ar-max-val" style="font-weight:bold">{max_val}</span> m<br>'
            f'<input type="range" id="telttur-ar-max" min="0" max="{slider_max}" '
            f'step="100" value="{max_val}" style="width:100%;margin:2px 0 6px"'
            " oninput=\"document.getElementById('telttur-ar-max-val').textContent="
            'this.value;teltturUpdate()">'
        )

    if cabin_density_slider is not None and cabin_density_slider.enabled:
        val_str = f"{cabin_density_slider.value:.3f}"
        slider_max_str = f"{cabin_density_slider.slider_max:.3f}"
        parts.append(
            "<b>Cabin density threshold:</b> "
            f'<span id="telttur-ct-val" style="font-weight:bold">{val_str}</span><br>'
            f'<input type="range" id="telttur-ct" min="0" max="{slider_max_str}" '
            f'step="0.001" value="{val_str}" style="width:100%;margin:3px 0 8px"'
            " oninput=\"document.getElementById('telttur-ct-val').textContent="
            'parseFloat(this.value).toFixed(3);teltturUpdate()">'
        )

    if ar5_buffers is not None and ar5_buffers.enabled:
        res_val = int(scoring.ar5_land_use.residential_buffer_m)
        ind_val = int(scoring.ar5_land_use.industrial_buffer_m)
        ar5_slider_max = int(ar5_buffers.slider_max_m)
        parts.append(
            "<b>AR5 buffers:</b><br>"
            f'Residential: <span id="telttur-ar5-res-val" style="font-weight:bold">{res_val}</span> m<br>'
            f'<input type="range" id="telttur-ar5-res" min="0" max="{ar5_slider_max}" '
            f'step="100" value="{res_val}" style="width:100%;margin:2px 0 6px"'
            " oninput=\"document.getElementById('telttur-ar5-res-val').textContent="
            'this.value;teltturUpdate()"><br>'
            f'Industrial: <span id="telttur-ar5-ind-val" style="font-weight:bold">{ind_val}</span> m<br>'
            f'<input type="range" id="telttur-ar5-ind" min="0" max="{ar5_slider_max}" '
            f'step="100" value="{ind_val}" style="width:100%;margin:2px 0 6px"'
            " oninput=\"document.getElementById('telttur-ar5-ind-val').textContent="
            'this.value;teltturUpdate()">'
        )

    parts.append("</div></div>")
    return "\n".join(parts)


def _build_js(
    *,
    lake_data_block: str,
    dt: InteractiveDimensionToggles,
    scoring: ScoringConfig,
    show_min_area: bool,
    min_area_init: int,
    access_range: InteractiveAccessibilityRange | None,
    cabin_density_slider: InteractiveCabinDensitySlider | None,
    ar5_buffers: InteractiveAr5Buffers | None,
) -> str:
    # Accessibility range slider defaults (used when slider elements are absent).
    if access_range is not None and access_range.enabled:
        ar_min_default = int(access_range.min_m)
        ar_max_default = int(access_range.max_m)
        js_access_score = (
            "scoreAccess(props.road_distance_m != null ? parseFloat(props.road_distance_m) : 0)"
        )
    else:
        ar_min_default = 0
        ar_max_default = 0
        js_access_score = "props.accessibility_score"

    # Cabin density default threshold (used when slider element is absent).
    ct_default = (
        cabin_density_slider.value
        if cabin_density_slider is not None
        else scoring.cabin_density.thresholds.good
    )
    js_cabin_score = (
        "scoreCabin(props.building_density != null ? parseFloat(props.building_density) : 0)"
        if cabin_density_slider is not None
        else "props.cabin_density_score"
    )

    # AR5 buffer defaults (used when slider elements are absent).
    ar5_res_default = int(scoring.ar5_land_use.residential_buffer_m)
    ar5_ind_default = int(scoring.ar5_land_use.industrial_buffer_m)
    js_ar5_score = (
        "scoreAr5("
        "props.industrial_distance_m != null ? parseFloat(props.industrial_distance_m) : 0,"
        "props.residential_distance_m != null ? parseFloat(props.residential_distance_m) : 0)"
        if ar5_buffers is not None
        else "props.ar5_land_use_score"
    )

    cabin_init = str(scoring.cabin_density.enabled).lower()
    access_init = str(scoring.accessibility.enabled).lower()
    ar5_init = str(scoring.ar5_land_use.enabled).lower()
    fishing_init = str(scoring.fishing.enabled).lower()

    js_cabin_enabled = (
        f"el('telttur-cabin') ? el('telttur-cabin').checked : {cabin_init}"
        if dt.cabin_density
        else cabin_init
    )
    js_access_enabled = (
        f"el('telttur-access') ? el('telttur-access').checked : {access_init}"
        if dt.accessibility
        else access_init
    )
    js_ar5_enabled = (
        f"el('telttur-ar5') ? el('telttur-ar5').checked : {ar5_init}"
        if dt.ar5_land_use
        else ar5_init
    )
    js_fishing_enabled = (
        f"el('telttur-fishing') ? el('telttur-fishing').checked : {fishing_init}"
        if dt.fishing
        else fishing_init
    )
    js_min_area = (
        f"el('telttur-min-area') ? parseFloat(el('telttur-min-area').value) : {min_area_init}"
        if show_min_area
        else str(min_area_init)
    )

    return f"""<script>
(function() {{
  {lake_data_block}
  var CT_DEF = {ct_default};
  var AR_MIN_DEF = {ar_min_default};
  var AR_MAX_DEF = {ar_max_default};
  var AR5_RES_DEF = {ar5_res_default};
  var AR5_IND_DEF = {ar5_ind_default};
  var COLORS = {{1:'#d73027',2:'#fc8d59',3:'#fee08b',4:'#91cf60',5:'#1a9850'}};

  function el(id) {{ return document.getElementById(id); }}

  function findLakesLayer() {{
    for (var k in window) {{
      if (k.indexOf('layer_control_') === 0 && k.indexOf('_layers') > 0) {{
        var obj = window[k];
        if (obj && obj.overlays && obj.overlays['Lakes']) {{
          return obj.overlays['Lakes'];
        }}
      }}
    }}
    // Fallback: no LayerControl present — search for Folium's FeatureGroup /
    // MarkerCluster variables directly (named feature_group_* or marker_cluster_*).
    for (var k in window) {{
      if ((k.indexOf('feature_group_') === 0 || k.indexOf('marker_cluster_') === 0)
          && typeof window[k].eachLayer === 'function') {{
        return window[k];
      }}
    }}
    return null;
  }}

  function scoreAccess(dist) {{
    var minKm = (el('telttur-ar-min') ? parseFloat(el('telttur-ar-min').value) : AR_MIN_DEF);
    var maxKm = (el('telttur-ar-max') ? parseFloat(el('telttur-ar-max').value) : AR_MAX_DEF);
    if (dist >= minKm && dist <= maxKm) return 5;
    if (dist > maxKm) {{
      if (dist <= maxKm * 1.25) return 4;
      if (dist <= maxKm * 1.5)  return 3;
      if (dist <= maxKm * 2.0)  return 2;
      return 1;
    }}
    // dist < minKm
    if (minKm === 0) return 5;
    if (dist >= minKm * 0.75) return 4;
    if (dist >= minKm * 0.5)  return 3;
    if (dist >= minKm * 0.25) return 2;
    return 1;
  }}

  function scoreCabin(density) {{
    var T = el('telttur-ct') ? parseFloat(el('telttur-ct').value) : CT_DEF;
    if (T <= 0) return density <= 0 ? 5 : 1;
    if (density <= T)         return 5;
    if (density <= T * 1.25)  return 4;
    if (density <= T * 1.5)   return 3;
    if (density <= T * 2.0)   return 2;
    return 1;
  }}

  function _scoreAr5One(dist, buf) {{
    if (buf <= 0) return 5;
    if (dist <= buf)         return 1;
    if (dist <= buf * 1.25)  return 2;
    if (dist <= buf * 1.5)   return 3;
    if (dist <= buf * 2.0)   return 4;
    return 5;
  }}

  function scoreAr5(indDist, resDist) {{
    var resBuf = el('telttur-ar5-res') ? parseFloat(el('telttur-ar5-res').value) : AR5_RES_DEF;
    var indBuf = el('telttur-ar5-ind') ? parseFloat(el('telttur-ar5-ind').value) : AR5_IND_DEF;
    return Math.min(_scoreAr5One(indDist, indBuf), _scoreAr5One(resDist, resBuf));
  }}

  window.teltturUpdate = function() {{
    var lakesLayer = findLakesLayer();
    if (!lakesLayer) return;

    var minArea   = {js_min_area};
    var cabinOn   = {js_cabin_enabled};
    var accessOn  = {js_access_enabled};
    var ar5On     = {js_ar5_enabled};
    var fishingOn = {js_fishing_enabled};

    lakesLayer.eachLayer(function(layer) {{
      var props = (layer.feature && layer.feature.properties) || null;
      if (!props && typeof TELTTUR_LAKE_DATA !== 'undefined') {{
        var ll = layer.getLatLng();
        var key = ll.lat.toFixed(6) + ',' + ll.lng.toFixed(6);
        props = TELTTUR_LAKE_DATA[key] || null;
      }}
      if (!props) return;

      var area = props.area_m2 || 0;
      if (minArea > 0 && area < minArea) {{
        layer.setStyle({{fillOpacity: 0, opacity: 0, weight: 0}});
        return;
      }}

      var scores = [];

      if (cabinOn) {{
        var cs = {js_cabin_score};
        if (cs != null) scores.push(parseInt(cs));
      }}
      if (accessOn) {{
        var as_ = {js_access_score};
        if (as_ != null) scores.push(parseInt(as_));
      }}
      if (ar5On) {{
        var rs = {js_ar5_score};
        if (rs != null) scores.push(parseInt(rs));
      }}
      if (fishingOn) {{
        var fs = props.fishing_score;
        if (fs != null) scores.push(parseInt(fs));
      }}

      var score = scores.length > 0 ? Math.min.apply(null, scores) : 0;
      layer.setStyle({{
        fillColor:   COLORS[score] || '#67a9cf',
        color:       '#333333',
        weight:      0.8,
        fillOpacity: 0.65,
        opacity:     1
      }});
    }});
  }};

  setTimeout(window.teltturUpdate, 300);
}})();
</script>"""
