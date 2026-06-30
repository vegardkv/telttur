"""Standalone Leaflet debug map for inspecting road classifications.

Switched on by ``debug_map: true`` in the config. Instead of the normal
``data.js`` payload, the pipeline writes a single self-contained HTML file that
shows every road colour-coded by N50 category, with excluded (non-drivable)
types drawn dashed and a click-to-inspect popup reporting the category and
whether it is included in accessibility scoring. Lake locations are overlaid as
markers. Region/bbox is taken from the config exactly as in a normal run.

No Folium — this is plain Leaflet (CDN) matching ``web/index.html``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd

from telttur.config import Config
from telttur.data_export import build_lake_data, build_road_data
from telttur.roads import ROAD_CATEGORIES

# Kartverket basemap — same tiles/attribution as web/app.js for visual consistency.
_TILE_URL = (
    "https://cache.kartverket.no/v1/wmts/1.0.0/topograatone/default/webmercator/{z}/{y}/{x}.png"
)
_TILE_ATTR = '&copy; <a href="https://www.kartverket.no/">Kartverket</a>'


def _build_lake_points(lakes: gpd.GeoDataFrame) -> list[list[Any]]:
    """Reduce the lakes GeoDataFrame to ``[lat, lng, name]`` triples."""
    if lakes.empty:
        return []
    rows, fields = build_lake_data(lakes)
    idx = {name: i for i, name in enumerate(fields)}
    name_i = idx.get("name")
    return [
        [row[idx["lat"]], row[idx["lng"]], row[name_i] if name_i is not None else None]
        for row in rows
    ]


def export_debug_map(
    roads: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
    config: Config,
    output_path: Path,
) -> None:
    """Write a self-contained Leaflet debug HTML map to ``output_path``."""
    assert config.bbox is not None  # guaranteed by Config.require_bbox validator
    bbox = config.bbox

    roads_geojson = build_road_data(roads)
    lake_points = _build_lake_points(lakes)
    excluded = sorted(set(config.scoring.accessibility.excluded_road_types))

    html = _TEMPLATE
    replacements = {
        "__ROADS__": json.dumps(roads_geojson, separators=(",", ":")),
        "__LAKES__": json.dumps(lake_points, separators=(",", ":")),
        "__EXCLUDED__": json.dumps(excluded),
        "__CATEGORIES__": json.dumps(ROAD_CATEGORIES, ensure_ascii=False),
        "__BOUNDS__": json.dumps([[bbox.south, bbox.west], [bbox.north, bbox.east]]),
        # JSON-encoded so quotes inside the attribution don't break the JS string.
        "__TILE_URL__": json.dumps(_TILE_URL),
        "__TILE_ATTR__": json.dumps(_TILE_ATTR),
    }
    for token, value in replacements.items():
        html = html.replace(token, value)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


# Single self-contained page. Injected JSON blobs use __TOKEN__ placeholders so
# the CSS/JS braces below don't clash with str.format.
_TEMPLATE = """<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Telttur road debug map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="">
  <style>
    html, body { margin: 0; height: 100%; }
    #map { height: 100%; }
    .legend {
      background: #fff; padding: 8px 10px; border-radius: 4px;
      box-shadow: 0 1px 5px rgba(0,0,0,0.3); font: 12px/1.4 sans-serif;
    }
    .legend h4 { margin: 0 0 6px; font-size: 12px; }
    .legend .row { display: flex; align-items: center; margin: 2px 0; }
    .legend .swatch {
      width: 22px; height: 0; border-top: 3px solid #999;
      margin-right: 6px; flex: 0 0 auto;
    }
    .legend .excluded { color: #b00; }
    .road-popup b { display: block; margin-bottom: 4px; }
    .road-popup .inc { color: #1a9850; font-weight: bold; }
    .road-popup .exc { color: #d73027; font-weight: bold; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
  <script>
    const ROADS = __ROADS__;
    const LAKES = __LAKES__;
    const EXCLUDED = new Set(__EXCLUDED__);
    const CATEGORIES = __CATEGORIES__;
    const BOUNDS = __BOUNDS__;

    const map = L.map("map", { preferCanvas: true });
    map.fitBounds(BOUNDS, { padding: [20, 20] });
    L.tileLayer(__TILE_URL__, { attribution: __TILE_ATTR__, maxZoom: 18 }).addTo(map);

    function catLabel(cat) {
      return (cat && CATEGORIES[cat] && CATEGORIES[cat].label) || cat || "(unknown)";
    }

    // Roads: colour by category, dash the excluded (non-drivable) types.
    L.geoJSON(ROADS, {
      style: (f) => {
        const cat = f.properties?.category;
        const isExcluded = cat != null && EXCLUDED.has(cat);
        return {
          color: f.properties?.color ?? "#999999",
          weight: isExcluded ? 4 : 3,
          opacity: 0.9,
          dashArray: isExcluded ? "4 6" : null,
        };
      },
      onEachFeature: (f, layer) => {
        const cat = f.properties?.category;
        const isExcluded = cat != null && EXCLUDED.has(cat);
        const status = isExcluded
          ? '<span class="exc">EXCLUDED ✗ (non-drivable)</span>'
          : '<span class="inc">INCLUDED ✓ (drivable)</span>';
        layer.bindPopup(
          '<div class="road-popup"><b>Road</b>'
          + "Category: <code>" + (cat ?? "(none)") + "</code><br>"
          + "Label: " + catLabel(cat) + "<br>"
          + "Status: " + status + "</div>"
        );
      },
    }).addTo(map);

    // Lakes: small markers with a name/area tooltip.
    const lakeLayer = L.layerGroup().addTo(map);
    for (const [lat, lng, name] of LAKES) {
      const m = L.circleMarker([lat, lng], {
        radius: 5, color: "#13366b", weight: 1,
        fillColor: "#3a7bd5", fillOpacity: 0.85,
      });
      if (name) m.bindTooltip(String(name));
      m.addTo(lakeLayer);
    }

    // Legend: every category swatch, excluded ones flagged.
    const legend = L.control({ position: "bottomright" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "legend");
      let html = "<h4>Road categories</h4>";
      for (const [code, info] of Object.entries(CATEGORIES)) {
        const exc = EXCLUDED.has(code);
        const dash = exc ? "border-top-style: dashed;" : "";
        html += '<div class="row' + (exc ? " excluded" : "") + '">'
          + '<span class="swatch" style="border-top-color:' + info.color + ';' + dash + '"></span>'
          + code + " – " + info.label + (exc ? " (excluded)" : "")
          + "</div>";
      }
      html += '<div class="row" style="margin-top:6px">'
        + '<span class="swatch" style="border-top-color:#3a7bd5;border-top-width:0;'
        + 'width:10px;height:10px;border-radius:50%;background:#3a7bd5"></span>Lake</div>';
      div.innerHTML = html;
      return div;
    };
    legend.addTo(map);
  </script>
</body>
</html>
"""
