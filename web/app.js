/**
 * Telttur – static Leaflet frontend.
 *
 * Reads data.json (relative to this file's location, or the path set in
 * DATA_URL) and renders lakes, roads, and an interactive control panel.
 */

"use strict";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

// Kartverket tile layers
const KARTVERKET_GRAY =
  "https://cache.kartverket.no/v1/wmts/1.0.0/topograatone/default/webmercator/{z}/{y}/{x}.png";
const KARTVERKET_TOPO =
  "https://cache.kartverket.no/v1/wmts/1.0.0/topo/default/webmercator/{z}/{y}/{x}.png";
const KARTVERKET_ATTR =
  '&copy; <a href="https://www.kartverket.no/">Kartverket</a>';

// Score level colours (1=Terrible … 5=Excellent)
const LEVEL_COLORS = {
  1: "#d73027",
  2: "#fc8d59",
  3: "#fee08b",
  4: "#91cf60",
  5: "#1a9850",
};
const LEVEL_NAMES = {
  1: "Terrible",
  2: "Poor",
  3: "Fair",
  4: "Good",
  5: "Excellent",
};
const BADGE_CLASSES = {
  1: "tt-b1",
  2: "tt-b2",
  3: "tt-b3",
  4: "tt-b4",
  5: "tt-b5",
};
const DEFAULT_LAKE_COLOR = "#67a9cf";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let map;
let lakesLayer;     // L.LayerGroup containing all CircleMarker instances
let allMarkers = []; // { marker, fields } — kept for re-filtering

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Make a score badge <span> if v is 1–5, else return plain string. */
function badge(v) {
  if (typeof v === "number" && v >= 1 && v <= 5) {
    return `<span class="${BADGE_CLASSES[v]}">${LEVEL_NAMES[v]}</span>`;
  }
  return v != null ? String(v) : "";
}

/** Format area_m2 to a human-readable string. */
function formatArea(m2) {
  if (m2 >= 1e6) return (m2 / 1e6).toFixed(2) + " km²";
  if (m2 >= 1e4) return (m2 / 1e4).toFixed(1) + " ha";
  return m2.toFixed(0) + " m²";
}

/** Format a distance in metres (rounds to integer). */
function formatDist(m) {
  if (m == null) return "–";
  if (m >= 1000) return (m / 1000).toFixed(1) + " km";
  return Math.round(m) + " m";
}

/** Return the current value of a slider element (or a default). */
function sliderVal(id, def) {
  const el = document.getElementById(id);
  return el ? parseFloat(el.value) : def;
}

/** Return checked state of a checkbox (or a default). */
function checkVal(id, def) {
  const el = document.getElementById(id);
  return el ? el.checked : def;
}

// ---------------------------------------------------------------------------
// Scoring re-calculation (mirrors Python scoring logic)
// ---------------------------------------------------------------------------

function scoreAccess(dist, minM, maxM) {
  if (dist >= minM && dist <= maxM) return 5;
  if (dist > maxM) {
    if (dist <= maxM * 1.25) return 4;
    if (dist <= maxM * 1.5) return 3;
    if (dist <= maxM * 2.0) return 2;
    return 1;
  }
  // dist < minM
  if (minM === 0) return 5;
  if (dist >= minM * 0.75) return 4;
  if (dist >= minM * 0.5) return 3;
  if (dist >= minM * 0.25) return 2;
  return 1;
}

function scoreCabin(density, threshold) {
  if (threshold <= 0) return density <= 0 ? 5 : 1;
  if (density <= threshold) return 5;
  if (density <= threshold * 1.25) return 4;
  if (density <= threshold * 1.5) return 3;
  if (density <= threshold * 2.0) return 2;
  return 1;
}

function scoreAr5One(dist, buf) {
  if (buf <= 0) return 5;
  if (dist <= buf) return 1;
  if (dist <= buf * 1.25) return 2;
  if (dist <= buf * 1.5) return 3;
  if (dist <= buf * 2.0) return 4;
  return 5;
}

function scoreAr5(indDist, resDist, indBuf, resBuf) {
  return Math.min(scoreAr5One(indDist, indBuf), scoreAr5One(resDist, resBuf));
}

function popcount(n) {
  let count = 0;
  while (n) { count += n & 1; n >>>= 1; }
  return count;
}

/** Score fishing by fraction of desired prized genera present at the lake.
 *  generaMask — bitmask of genera found near the lake (from data)
 *  desiredMask — bitmask of genera the user wants (from checkboxes)
 *  Returns null when desiredMask is 0 (no genera selected → skip dimension).
 */
function scoreFishing(generaMask, desiredMask) {
  if (!desiredMask) return null;
  const matched = popcount(generaMask & desiredMask);
  const fraction = matched / popcount(desiredMask);
  if (fraction <= 0) return 1;
  if (fraction <= 0.25) return 2;
  if (fraction <= 0.5) return 3;
  if (fraction <= 0.75) return 4;
  return 5;
}

// ---------------------------------------------------------------------------
// Read current slider/toggle state
// ---------------------------------------------------------------------------

/** Read the current control panel state for scoring. */
function readControlState(cfg) {
  const ctrl = cfg.interactive;
  const scoring = cfg.scoring;

  const arCfg = ctrl.accessibility_range || {};
  const ctCfg = ctrl.cabin_density_slider || {};
  const ar5Cfg = ctrl.ar5_buffers || {};

  // Build fishing genera mask from checkboxes (default: all selected)
  const fishingGenera = (scoring.fishing && scoring.fishing.genera) || [];
  let fishingMask = 0;
  for (const g of fishingGenera) {
    if (checkVal(`tt-fg-${g.code}`, true)) fishingMask |= (1 << g.code);
  }

  return {
    minArea: ctrl.min_lake_area
      ? sliderVal("tt-min-area", cfg.min_lake_area_m2)
      : cfg.min_lake_area_m2,
    arMin: arCfg.enabled ? sliderVal("tt-ar-min", arCfg.min_m || 0) : 0,
    arMax: arCfg.enabled ? sliderVal("tt-ar-max", arCfg.max_m || 5000) : 5000,
    ctThreshold: ctCfg.enabled
      ? sliderVal("tt-ct", ctCfg.value || 0.05)
      : (scoring.cabin_density ? scoring.cabin_density.thresholds.good || 0.01 : 0.01),
    ar5ResBuf: ar5Cfg.enabled
      ? sliderVal("tt-ar5-res", (scoring.ar5_land_use || {}).residential_buffer_m || 1000)
      : ((scoring.ar5_land_use || {}).residential_buffer_m || 1000),
    ar5IndBuf: ar5Cfg.enabled
      ? sliderVal("tt-ar5-ind", (scoring.ar5_land_use || {}).industrial_buffer_m || 2000)
      : ((scoring.ar5_land_use || {}).industrial_buffer_m || 2000),
    cabinOn: checkVal("tt-cabin", !!(scoring.cabin_density && scoring.cabin_density.enabled)),
    accessOn: checkVal("tt-access", !!(scoring.accessibility && scoring.accessibility.enabled)),
    ar5On: checkVal("tt-ar5", !!(scoring.ar5_land_use && scoring.ar5_land_use.enabled)),
    fishingOn: checkVal("tt-fishing", !!(scoring.fishing && scoring.fishing.enabled)),
    fishingMask,
  };
}

/** Compute per-dimension scores for a single lake given the current control state. */
function computeScores(fields, cs) {
  const live = {};
  const scores = [];

  if (cs.cabinOn && fields.building_density != null) {
    live.cabin_density_score = scoreCabin(fields.building_density, cs.ctThreshold);
    scores.push(live.cabin_density_score);
  }

  if (cs.accessOn && fields.road_distance_m != null) {
    live.accessibility_score = scoreAccess(fields.road_distance_m, cs.arMin, cs.arMax);
    scores.push(live.accessibility_score);
  }

  if (cs.ar5On && fields.industrial_distance_m != null && fields.residential_distance_m != null) {
    live.ar5_land_use_score = scoreAr5(fields.industrial_distance_m, fields.residential_distance_m, cs.ar5IndBuf, cs.ar5ResBuf);
    scores.push(live.ar5_land_use_score);
  }

  if (cs.fishingOn && fields.fish_genera_mask != null && cs.fishingMask) {
    const fs = scoreFishing(fields.fish_genera_mask, cs.fishingMask);
    if (fs != null) {
      live.fishing_score = fs;
      scores.push(live.fishing_score);
    }
  }

  live.tentability_score = scores.length > 0 ? Math.min(...scores) : null;
  return live;
}

// ---------------------------------------------------------------------------
// Interactive update — called on every slider/checkbox change
// ---------------------------------------------------------------------------

function teltturUpdate(cfg, idx) {
  const cs = readControlState(cfg);

  for (const { marker, fields } of allMarkers) {
    const area = fields.area || 0;

    if (cs.minArea > 0 && area < cs.minArea) {
      marker.setStyle({ fillOpacity: 0, opacity: 0, weight: 0 });
      continue;
    }

    const live = computeScores(fields, cs);
    const score = live.tentability_score || 0;
    marker.setStyle({
      fillColor: LEVEL_COLORS[score] || DEFAULT_LAKE_COLOR,
      color: "#333333",
      weight: 0.8,
      fillOpacity: 0.65,
      opacity: 1,
    });
  }
}

// ---------------------------------------------------------------------------
// Popup builder
// ---------------------------------------------------------------------------

/**
 * Build popup HTML for a lake.
 * @param {object} fields      - Raw data fields from the dataset.
 * @param {object} liveScores  - Live-computed scores from computeScores().
 */
function buildPopup(fields, liveScores, cfg) {
  const rows = [];

  // Name
  if (fields.name) {
    rows.push(["Name", fields.name]);
  }

  // Tentability composite
  if (liveScores.tentability_score != null) {
    rows.push(["Tentability", liveScores.tentability_score]);
  }

  // Per-dimension scores
  const scoreLabels = {
    cabin_density_score: "Cabin density",
    accessibility_score: "Accessibility",
    ar5_land_use_score: "Land use (AR5)",
    fishing_score: "Fishing",
  };
  for (const [col, label] of Object.entries(scoreLabels)) {
    if (liveScores[col] != null) {
      rows.push([label, liveScores[col]]);
    }
  }

  // Separator before details
  const detailRows = [];
  if (fields.area != null) {
    detailRows.push(["Area", formatArea(fields.area)]);
  }
  const detailLabels = {
    road_distance_m: "Road distance",
    building_density: "Building density",
    industrial_distance_m: "Industrial dist.",
    residential_distance_m: "Residential dist.",
    fish_species_count: "Fish species",
  };
  for (const [col, label] of Object.entries(detailLabels)) {
    if (fields[col] != null) {
      const val = col.endsWith("_m") ? formatDist(fields[col]) : fields[col];
      detailRows.push([label, val]);
    }
  }

  // Prized genera present at this lake
  if (cfg && fields.fish_genera_mask != null) {
    const fishingGenera = (cfg.scoring && cfg.scoring.fishing && cfg.scoring.fishing.genera) || [];
    const present = fishingGenera
      .filter(g => (fields.fish_genera_mask & (1 << g.code)) !== 0)
      .map(g => g.label);
    if (present.length > 0) {
      detailRows.push(["Fish genera", present.join(", ")]);
    }
  }

  let html = "<div class='tt-popup'><table>";
  for (const [label, val] of rows) {
    html += `<tr><th>${label}</th><td>${badge(val)}</td></tr>`;
  }
  if (detailRows.length > 0) {
    html += "<tr><td colspan='2'><hr></td></tr>";
    for (const [label, val] of detailRows) {
      html += `<tr><th>${label}</th><td>${val}</td></tr>`;
    }
  }
  html += "</table></div>";
  return html;
}

// ---------------------------------------------------------------------------
// Map initialisation
// ---------------------------------------------------------------------------

function initMap(data) {
  const bbox = data.meta.bbox; // [south, west, north, east]
  const bounds = L.latLngBounds([bbox[0], bbox[1]], [bbox[2], bbox[3]]);

  map = L.map("map", { preferCanvas: true });
  map.fitBounds(bounds, { padding: [20, 20] });

  L.tileLayer(KARTVERKET_GRAY, {
    attribution: KARTVERKET_ATTR,
    maxZoom: 18,
  }).addTo(map);

  // Roads
  if (data.roads && data.roads.features && data.roads.features.length > 0) {
    L.geoJSON(data.roads, {
      style: (feature) => ({
        color: (feature.properties && feature.properties.color) || "#999999",
        weight: 2,
        opacity: 0.8,
      }),
    }).addTo(map);
  }

  // Lakes
  const fields = data.lake_fields;
  const idx = {};
  for (let i = 0; i < fields.length; i++) idx[fields[i]] = i;

  lakesLayer = L.layerGroup().addTo(map);
  allMarkers = [];

  for (const row of data.lakes) {
    const lat = row[idx["lat"]];
    const lng = row[idx["lng"]];

    // Build a plain-object dict from the row
    const f = {};
    for (const key of fields) {
      f[key] = row[idx[key]];
    }

    // Initial colour — will be set by teltturUpdate() shortly after init
    const marker = L.circleMarker([lat, lng], {
      radius: 8,
      color: "#333333",
      weight: 0.8,
      fillColor: DEFAULT_LAKE_COLOR,
      fillOpacity: 0.65,
      opacity: 1,
    });

    marker.bindPopup("", { maxWidth: 300 });
    marker.on("popupopen", () => {
      const cs = readControlState(data.config);
      marker.getPopup().setContent(buildPopup(f, computeScores(f, cs), data.config));
    });
    marker.addTo(lakesLayer);
    allMarkers.push({ marker, fields: f });
  }

  // Build UI
  buildControls(data.config, data.lake_fields);
  buildLegend(data);

  // Initial filter pass
  setTimeout(() => teltturUpdate(data.config, idx), 100);
}

// ---------------------------------------------------------------------------
// Controls panel
// ---------------------------------------------------------------------------

function buildControls(cfg, lakeFields) {
  const ctrl = cfg.interactive;
  if (!ctrl || !ctrl.enabled) return;

  const scoring = cfg.scoring || {};
  const dt = ctrl.dimension_toggles || {};

  const container = document.createElement("div");
  container.id = "tt-controls";

  // Header
  const header = document.createElement("div");
  header.id = "tt-controls-header";
  header.innerHTML =
    '<b>⚙ Scoring</b>' +
    '<button id="tt-toggle-btn" onclick="' +
    "var b=document.getElementById('tt-body'),s=b.style;" +
    "s.display=s.display==='none'?'block':'none'" +
    '">▼</button>';
  container.appendChild(header);

  const body = document.createElement("div");
  body.id = "tt-body";
  container.appendChild(body);

  const lakeFieldSet = new Set(lakeFields);

  // Dimension toggles
  const dims = [
    [dt.cabin_density && scoring.cabin_density, "tt-cabin", "Cabin density"],
    [dt.accessibility && scoring.accessibility, "tt-access", "Accessibility"],
    [dt.ar5_land_use && scoring.ar5_land_use, "tt-ar5", "Land use (AR5)"],
    [dt.fishing && scoring.fishing, "tt-fishing", "Fishing"],
  ].filter(([show]) => show);

  if (dims.length > 0) {
    body.innerHTML += "<b>Dimensions:</b><br>";
    for (const [, id, label] of dims) {
      body.innerHTML += `<label><input type="checkbox" id="${id}" checked onchange="teltturUpdate(_ttCfg)"> ${label}</label><br>`;
    }
    body.innerHTML += '<div class="tt-spacer"></div>';
  }

  // Min lake area
  const minArea = cfg.min_lake_area_m2 || 0;
  if (ctrl.min_lake_area) {
    body.innerHTML +=
      `<b>Min lake area:</b> <span id="tt-min-area-val" style="font-weight:bold">${minArea}</span> m²<br>` +
      `<input type="range" id="tt-min-area" min="0" max="100000" step="500" value="${minArea}" ` +
      `oninput="document.getElementById('tt-min-area-val').textContent=this.value;teltturUpdate(_ttCfg)">`;
  }

  // Accessibility range
  const ar = ctrl.accessibility_range;
  if (ar && ar.enabled && lakeFieldSet.has("road_distance_m")) {
    const arMin = ar.min_m | 0;
    const arMax = ar.max_m | 0;
    const arSliderMax = ar.slider_max_m | 0;
    body.innerHTML +=
      `<b>Accessibility distance:</b><br>` +
      `Min: <span id="tt-ar-min-val" style="font-weight:bold">${arMin}</span> m<br>` +
      `<input type="range" id="tt-ar-min" min="0" max="${arSliderMax}" step="100" value="${arMin}" ` +
      `oninput="document.getElementById('tt-ar-min-val').textContent=this.value;teltturUpdate(_ttCfg)"><br>` +
      `Max: <span id="tt-ar-max-val" style="font-weight:bold">${arMax}</span> m<br>` +
      `<input type="range" id="tt-ar-max" min="0" max="${arSliderMax}" step="100" value="${arMax}" ` +
      `oninput="document.getElementById('tt-ar-max-val').textContent=this.value;teltturUpdate(_ttCfg)">`;
  }

  // Cabin density slider
  const cd = ctrl.cabin_density_slider;
  if (cd && cd.enabled && lakeFieldSet.has("building_density")) {
    const val = cd.value.toFixed(3);
    body.innerHTML +=
      `<b>Cabin density threshold:</b> <span id="tt-ct-val" style="font-weight:bold">${val}</span><br>` +
      `<input type="range" id="tt-ct" min="0" max="${cd.slider_max.toFixed(3)}" step="0.001" value="${val}" ` +
      `oninput="document.getElementById('tt-ct-val').textContent=parseFloat(this.value).toFixed(3);teltturUpdate(_ttCfg)">`;
  }

  // AR5 buffers
  const ar5b = ctrl.ar5_buffers;
  const ar5s = scoring.ar5_land_use;
  if (ar5b && ar5b.enabled && ar5s && lakeFieldSet.has("industrial_distance_m")) {
    const resVal = ar5s.residential_buffer_m | 0;
    const indVal = ar5s.industrial_buffer_m | 0;
    const ar5SliderMax = ar5b.slider_max_m | 0;
    body.innerHTML +=
      `<b>AR5 buffers:</b><br>` +
      `Residential: <span id="tt-ar5-res-val" style="font-weight:bold">${resVal}</span> m<br>` +
      `<input type="range" id="tt-ar5-res" min="0" max="${ar5SliderMax}" step="100" value="${resVal}" ` +
      `oninput="document.getElementById('tt-ar5-res-val').textContent=this.value;teltturUpdate(_ttCfg)"><br>` +
      `Industrial: <span id="tt-ar5-ind-val" style="font-weight:bold">${indVal}</span> m<br>` +
      `<input type="range" id="tt-ar5-ind" min="0" max="${ar5SliderMax}" step="100" value="${indVal}" ` +
      `oninput="document.getElementById('tt-ar5-ind-val').textContent=this.value;teltturUpdate(_ttCfg)">`;
  }

  // Fishing genera toggles
  const fgCfg = ctrl.fishing_genera;
  const fishingGenera = (scoring.fishing && scoring.fishing.genera) || [];
  if (fgCfg && fgCfg.enabled && scoring.fishing && fishingGenera.length > 0 && lakeFieldSet.has("fish_genera_mask")) {
    body.innerHTML += '<div class="tt-spacer"></div><b>Fishing \u2013 desired genera:</b><br>';
    for (const g of fishingGenera) {
      body.innerHTML += `<label><input type="checkbox" id="tt-fg-${g.code}" checked onchange="teltturUpdate(_ttCfg)"> ${g.label}</label><br>`;
    }
  }

  document.body.appendChild(container);
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function buildLegend(data) {
  const hasTentability = data.lake_fields.includes("building_density") ||
    data.lake_fields.includes("road_distance_m") ||
    data.lake_fields.includes("fish_genera_mask");

  const legend = document.createElement("div");
  legend.id = "tt-legend";

  let html = "<b>Legend</b>";

  if (hasTentability) {
    html += "<b>Lakes – tentability:</b><br>";
    for (let level = 5; level >= 1; level--) {
      html +=
        `<div class="tt-legend-row">` +
        `<span class="tt-legend-swatch" style="background:${LEVEL_COLORS[level]}"></span>` +
        `${LEVEL_NAMES[level]}</div>`;
    }
  } else {
    html +=
      '<div class="tt-legend-row">' +
      '<span class="tt-legend-swatch" style="background:#67a9cf"></span>' +
      "Lakes</div>";
  }

  legend.innerHTML = html;
  document.body.appendChild(legend);
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

// Expose config globally so inline oninput handlers can call teltturUpdate.
let _ttCfg = null;

function _start(data) {
  _ttCfg = data.config;
  initMap(data);
}

if (window.TELTTUR_DATA) {
  _start(window.TELTTUR_DATA);
} else {
  document.body.innerHTML =
    `<div style="padding:2em;font-family:sans-serif;color:#c00">` +
    `<h2>Could not load map data</h2>` +
    `<p>Run <code>uv run telttur generate</code> to produce <code>output/data.js</code>.</p>` +
    `</div>`;
}
