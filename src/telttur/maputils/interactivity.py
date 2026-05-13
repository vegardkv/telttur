"""Interactive scoring controls panel injected into the Folium map."""

from __future__ import annotations

import json
from dataclasses import dataclass

import folium
import geopandas as gpd

from telttur.config import (
    AccessibilityThresholds,
    CabinDensityThresholds,
    Config,
    InteractiveDimensionToggles,
    ScoringConfig,
)


@dataclass
class _ThresholdSlider:
    """One threshold slider to render in the control panel."""

    level: str          # e.g. "excellent"
    value: float        # current threshold value from config
    lo: float           # slider min
    hi: float           # slider max
    step: float         # slider step
    prefix: str         # HTML id prefix ("at" or "ct")
    is_int: bool        # whether to display as integer


# Slider ranges per level for accessibility (metres) and cabin density.
_ACCESS_SLIDER_RANGES: dict[str, tuple[float, float, float]] = {
    "excellent": (0, 2000, 50),
    "good":      (0, 5000, 100),
    "fair":      (0, 10000, 200),
    "poor":      (0, 20000, 500),
}
_CABIN_SLIDER_RANGES: dict[str, tuple[float, float, float]] = {
    "excellent": (0.0, 0.05, 0.001),
    "good":      (0.0, 0.1, 0.002),
    "fair":      (0.0, 0.2, 0.005),
    "poor":      (0.0, 0.5, 0.01),
}

_LEVELS = ("excellent", "good", "fair", "poor")


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
    if lakes.empty or "tentability_score" not in lakes.columns:
        return

    scoring = config.scoring
    at = scoring.accessibility.thresholds
    ct = scoring.cabin_density.thresholds
    dt = controls.dimension_toggles

    # Collect threshold sliders, driven by the toggle BaseModel fields.
    access_sliders = _collect_threshold_sliders(
        controls.accessibility_thresholds.model_dump(), at.model_dump(),
        _ACCESS_SLIDER_RANGES, prefix="at", is_int=True,
    )
    cabin_sliders = _collect_threshold_sliders(
        controls.cabin_density_thresholds.model_dump(), ct.model_dump(),
        _CABIN_SLIDER_RANGES, prefix="ct", is_int=False,
    )
    # Only render threshold sliders when raw data columns are present.
    if "road_distance_m" not in lakes.columns:
        access_sliders = []
    if "building_density" not in lakes.columns:
        cabin_sliders = []

    lake_data_block = _build_lake_data_block(
        lakes, config.lake_display_mode == "marker",
    )

    panel_html = _build_panel_html(
        dt=dt,
        scoring=scoring,
        show_min_area=controls.min_lake_area,
        min_area_init=int(config.min_lake_area_m2),
        access_sliders=access_sliders,
        cabin_sliders=cabin_sliders,
    )

    js = _build_js(
        lake_data_block=lake_data_block,
        at=at,
        ct=ct,
        dt=dt,
        scoring=scoring,
        show_min_area=controls.min_lake_area,
        min_area_init=int(config.min_lake_area_m2),
        has_access_thresh=bool(access_sliders),
        has_cabin_thresh=bool(cabin_sliders),
    )

    root = m.get_root()
    root.html.add_child(folium.Element(panel_html + "\n" + js))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _collect_threshold_sliders(
    toggles: dict[str, bool],
    values: dict[str, float],
    ranges: dict[str, tuple[float, float, float]],
    *,
    prefix: str,
    is_int: bool,
) -> list[_ThresholdSlider]:
    """Build slider descriptors for each enabled threshold level."""
    sliders: list[_ThresholdSlider] = []
    for lvl in _LEVELS:
        if not toggles.get(lvl, False):
            continue
        lo, hi, step = ranges.get(lvl, (0, 10000, 100))
        sliders.append(_ThresholdSlider(
            level=lvl, value=values[lvl],
            lo=lo, hi=hi, step=step,
            prefix=prefix, is_int=is_int,
        ))
    return sliders


def _build_lake_data_block(
    lakes: gpd.GeoDataFrame, is_marker_mode: bool,
) -> str:
    """Return a JS variable declaration with per-lake data keyed by 'lat,lng'."""
    if not is_marker_mode:
        return ""

    lake_lookup: dict[str, dict] = {}
    for _, row in lakes.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        centroid = geom.centroid
        key = f"{round(centroid.y, 6):.6f},{round(centroid.x, 6):.6f}"

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
            "area_m2": _float("area_m2"),
            "cabin_density_score": _int("cabin_density_score"),
            "accessibility_score": _int("accessibility_score"),
            "ar5_land_use_score": _int("ar5_land_use_score"),
            "fishing_score": _int("fishing_score"),
            "road_distance_m": _float("road_distance_m"),
            "building_density": _float("building_density"),
        }

    return f"var TELTTUR_LAKE_DATA = {json.dumps(lake_lookup)};\n"


def _slider_html(s: _ThresholdSlider) -> str:
    """Render one threshold slider as HTML."""
    el_id = f"telttur-{s.prefix}-{s.level}"
    val_id = f"{el_id}-val"
    if s.is_int:
        v_display = str(int(s.value))
        oninput_fmt = "this.value"
        val_str = str(int(s.value))
    else:
        v_display = f"{s.value:.3f}"
        oninput_fmt = "parseFloat(this.value).toFixed(3)"
        val_str = f"{s.value:.3f}"
    unit = "m" if s.is_int else ""
    return (
        f'<label>{s.level.capitalize()} \u2264 '
        f'<span id="{val_id}" style="font-weight:bold">{v_display}</span>{unit}</label><br>'
        f'<input type="range" id="{el_id}" min="{s.lo}" max="{s.hi}" '
        f'step="{s.step}" value="{val_str}" style="width:100%;margin:2px 0 6px"'
        f" oninput=\"document.getElementById('{val_id}').textContent="
        f'{oninput_fmt};teltturUpdate()">'
    )


def _build_panel_html(
    *,
    dt: InteractiveDimensionToggles,
    scoring: ScoringConfig,
    show_min_area: bool,
    min_area_init: int,
    access_sliders: list[_ThresholdSlider],
    cabin_sliders: list[_ThresholdSlider],
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
        '<button onclick="var b=document.getElementById(\'telttur-body\'),'
        "s=b.style;s.display=s.display==='none'?'block':'none'"
        '" style="background:none;border:none;cursor:pointer;font-size:13px;padding:0"'
        ">\u25bc</button></div>",

        '<div id="telttur-body">',
    ]

    # Dimension toggle checkboxes \u2014 each entry reads directly from the models.
    _dim_defs = [
        (dt.cabin_density,  scoring.cabin_density.enabled,  "telttur-cabin",    "Cabin density"),
        (dt.accessibility,  scoring.accessibility.enabled,  "telttur-access",   "Accessibility"),
        (dt.ar5_land_use,   scoring.ar5_land_use.enabled,   "telttur-ar5",      "Land use (AR5)"),
        (dt.fishing,        scoring.fishing.enabled,        "telttur-fishing",  "Fishing"),
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
            '<b>Min lake area:</b> '
            f'<span id="telttur-min-area-val" style="font-weight:bold">{min_area_init}</span> m\u00b2<br>'
            f'<input type="range" id="telttur-min-area" min="0" max="100000" '
            f'step="500" value="{min_area_init}" style="width:100%;margin:3px 0 8px"'
            ' oninput="document.getElementById(\'telttur-min-area-val\').textContent='
            'this.value;teltturUpdate()">'
        )

    if access_sliders:
        parts.append("<b>Accessibility thresholds (m):</b><br>")
        for s in access_sliders:
            parts.append(_slider_html(s))

    if cabin_sliders:
        parts.append("<b>Cabin density thresholds:</b><br>")
        for s in cabin_sliders:
            parts.append(_slider_html(s))

    parts.append("</div></div>")
    return "\n".join(parts)


def _build_js(
    *,
    lake_data_block: str,
    at: AccessibilityThresholds,
    ct: CabinDensityThresholds,
    dt: InteractiveDimensionToggles,
    scoring: ScoringConfig,
    show_min_area: bool,
    min_area_init: int,
    has_access_thresh: bool,
    has_cabin_thresh: bool,
) -> str:
    at_defaults = json.dumps(at.model_dump())
    ct_defaults = json.dumps(ct.model_dump())

    cabin_init = str(scoring.cabin_density.enabled).lower()
    access_init = str(scoring.accessibility.enabled).lower()
    ar5_init = str(scoring.ar5_land_use.enabled).lower()
    fishing_init = str(scoring.fishing.enabled).lower()

    js_cabin_score = (
        "scoreCabin(props.building_density != null ? props.building_density : 0)"
        if has_cabin_thresh else "props.cabin_density_score"
    )
    js_access_score = (
        "scoreAccess(props.road_distance_m != null ? props.road_distance_m : 0)"
        if has_access_thresh else "props.accessibility_score"
    )
    js_cabin_enabled = (
        f"el('telttur-cabin') ? el('telttur-cabin').checked : {cabin_init}"
        if dt.cabin_density else cabin_init
    )
    js_access_enabled = (
        f"el('telttur-access') ? el('telttur-access').checked : {access_init}"
        if dt.accessibility else access_init
    )
    js_ar5_enabled = (
        f"el('telttur-ar5') ? el('telttur-ar5').checked : {ar5_init}"
        if dt.ar5_land_use else ar5_init
    )
    js_fishing_enabled = (
        f"el('telttur-fishing') ? el('telttur-fishing').checked : {fishing_init}"
        if dt.fishing else fishing_init
    )
    js_min_area = (
        f"el('telttur-min-area') ? parseFloat(el('telttur-min-area').value) : {min_area_init}"
        if show_min_area else str(min_area_init)
    )

    return f"""<script>
(function() {{
  {lake_data_block}
  var AT_DEF = {at_defaults};
  var CT_DEF = {ct_defaults};
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
    return null;
  }}

  function atVal(lvl) {{
    var e = el('telttur-at-' + lvl);
    return e ? parseFloat(e.value) : AT_DEF[lvl];
  }}
  function ctVal(lvl) {{
    var e = el('telttur-ct-' + lvl);
    return e ? parseFloat(e.value) : CT_DEF[lvl];
  }}

  function scoreAccess(dist) {{
    if (dist <= atVal('excellent')) return 5;
    if (dist <= atVal('good'))      return 4;
    if (dist <= atVal('fair'))      return 3;
    if (dist <= atVal('poor'))      return 2;
    return 1;
  }}

  function scoreCabin(density) {{
    if (density <= ctVal('excellent')) return 5;
    if (density <= ctVal('good'))      return 4;
    if (density <= ctVal('fair'))      return 3;
    if (density <= ctVal('poor'))      return 2;
    return 1;
  }}

  window.teltturUpdate = function() {{
    var lakesLayer = findLakesLayer();
    if (!lakesLayer) return;

    var minArea    = {js_min_area};
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
        var rs = props.ar5_land_use_score;
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
