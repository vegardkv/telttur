/**
 * Telttur – static Leaflet frontend.
 *
 * Reads data.json (relative to this file's location, or the path set in
 * DATA_URL) and renders lakes, roads, and an interactive control panel.
 */

"use strict";

// ---------------------------------------------------------------------------
// Internationalisation
// ---------------------------------------------------------------------------

const I18N = {
  title: "Telttur – Kart over teltturer i Norge",
  scoring: "Kriterier",
  min_lake_size: "Min innsjøstørrelse:",
  cabin_density: "Hyttetetthet",
  cabin_density_info: "Tetthet av enkeltbygninger og hytter innenfor en kort avstand fra innsjøen. 'Lav terskel' betyr at det kun er det mest avsidesliggende vannene som markeres som 'Utmerket'. Datakilde: N50 bygningslag (Kartverket). Merk: dette er et annet mål enn 'Avstand fra bebyggelse', som bruker AR5-arealklassifiseringsdata.",
  cabin_density_tolerance: "Toleranse:",
  cabin_density_levels: ["Svært lav", "Lav", "Middels", "Høy", "Svært høy"],
  cabin_density_level_low: "Lav",
  cabin_density_level_high: "Høy",
  accessibility: "Tilgjengelighet",
  accessibility_info: "Korteste avstand til nærmeste vei i luftlinje. Innsjøer innenfor ønsket rekkevidde får 'Utmerket'. Scoren synker utenfor rekkevidden. Datakilde: N50 vegnett (Kartverket).",
  ar5_land_use: "Avstand fra bebyggelse",
  ar5_land_use_info: "Avstand fra bolig- og industriområder basert på AR5-arealdata. Lengre unna utbygde områder gir høyere score: mer enn 2\xd7 avstanden = Utmerket. Datakilde: AR5 arealbruksklassifisering (Kartverket).",
  ar5_residential: "Boligområder:",
  ar5_industrial: "Industri:",
  fishing: "Fiske",
  fishing_info: "Fiskemuligheter basert på kjente fiskearter i innsjøen. Scoren er basert på andelen av dine valgte fiskeslekter som er til stede. Datakilde: NINA Vanndata fisk (NINA).",
  overall_score: "Total score",
  score_cabin_density: "Hyttetetthet",
  score_accessibility: "Tilgjengelighet",
  score_ar5: "Bebyggelse",
  score_fishing: "Fiske",
  area: "Areal",
  road_distance: "Avstand til vei",
  building_density: "Hyttetetthet",
  industrial_distance: "Avstand til industri",
  residential_distance: "Avstand til bebyggelse",
  fish_species: "Fiskearter",
  prized_fish: "Sportsfisk",
  legend_suitability: "Egnethet",
  legend_lakes: "Innsjøer",
  level_1: "Elendig",
  level_2: "Dårlig",
  level_3: "Middels",
  level_4: "Bra",
  level_5: "Utmerket",
  lake_size_filter: "Innsjøstørrelse",
  lake_size_filter_hint: "Skjul innsjøer utenfor dette størrelsesintervallet",
  error_no_data: "Klarte ikke å laste kartdata",
  genus_Salmo: "Ørret/Laks",
  genus_Salvelinus: "Røye",
  genus_Thymallus: "Harr",
  genus_Esox: "Gjedde",
  genus_Perca: "Abbor",
  genus_Coregonus: "Sik",
  fish_select_all: "Velg alle",
  fish_deselect_all: "Fjern alle",
  fish_selected_all: "Alle valgt",
  fish_selected_none: "Ingen valgt",
  credits: "Kildehenvisninger",
  credits_data: "Datakilder",
  credits_n50: "N50 kartdata (veier, innsjøer, bygninger)",
  credits_ar5: "AR5 arealbruksklassifisering",
  credits_nina: "Fiskeartsobservasjoner",
  credits_basemap: "Bakgrunnskartfliser",
  credits_library: "Kartbibliotek",
  credits_source_code: "Kildekode",
};

function t(key) {
  return I18N[key] ?? key;
}

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
let _arSlider = null;             // noUiSlider instance for accessibility range
let _lakeSizeSlider = null;       // noUiSlider instance for lake size range
let _ctSlider = null;             // noUiSlider instance for cabin density threshold
let _ar5ResSlider = null;         // noUiSlider instance for AR5 residential buffer
let _ar5IndSlider = null;         // noUiSlider instance for AR5 industrial buffer

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Make a score badge <span> if v is 1–5, else return plain string. */
function badge(v) {
  if (typeof v === "number" && v >= 1 && v <= 5) {
    return `<span class="${BADGE_CLASSES[v]}">${t(`level_${v}`)}</span>`;
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

/** Return the low handle value of the accessibility range slider (or default 0). */
function _arSliderMin() {
  return _arSlider ? parseFloat(_arSlider.get()[0]) : 0;
}

/** Return the high handle value of the accessibility range slider (or default 5000). */
function _arSliderMax() {
  return _arSlider ? parseFloat(_arSlider.get()[1]) : 5000;
}

/** Return the low handle value of the lake size slider (or default 0). */
function _lsMin() {
  return _lakeSizeSlider ? parseFloat(_lakeSizeSlider.get()[0]) : 0;
}

/** Return the high handle value of the lake size slider (or default 50 km²). */
function _lsMax() {
  return _lakeSizeSlider ? parseFloat(_lakeSizeSlider.get()[1]) : 50000000;
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

  const ctCfg = ctrl.cabin_density_slider;

  // Build fishing genera mask from checkboxes (default: all selected)
  const fishingGenera = scoring.fishing?.genera ?? [];
  let fishingMask = 0;
  for (const g of fishingGenera) {
    if (checkVal(`tt-fg-${g.code}`, true)) fishingMask |= (1 << g.code);
  }

  return {
    minArea: _lsMin(),
    maxArea: _lsMax(),
    arMin: _arSliderMin(),
    arMax: _arSliderMax(),
    ctThreshold: (() => {
      const quantiles = ctCfg.quantiles ?? [];
      const step = _ctSlider ? Math.round(parseFloat(_ctSlider.get())) : (ctCfg.default_step ?? 3);
      return quantiles[step - 1] ?? quantiles[quantiles.length - 1] ?? 0.05;
    })(),
    ar5ResBuf: _ar5ResSlider ? parseFloat(_ar5ResSlider.get()) : (scoring.ar5_land_use?.residential_buffer_m ?? 1000),
    ar5IndBuf: _ar5IndSlider ? parseFloat(_ar5IndSlider.get()) : (scoring.ar5_land_use?.industrial_buffer_m ?? 2000),
    cabinOn: checkVal("tt-cabin", false),
    accessOn: checkVal("tt-access", true),
    ar5On: checkVal("tt-ar5", true),
    fishingOn: checkVal("tt-fishing", false),
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

    if (area < cs.minArea || area > cs.maxArea) {
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
  const scoreRows = [];

  // Per-dimension scores
  const scoreLabels = {
    cabin_density_score: t("score_cabin_density"),
    accessibility_score: t("score_accessibility"),
    ar5_land_use_score: t("score_ar5"),
    fishing_score: t("score_fishing"),
  };
  for (const [col, label] of Object.entries(scoreLabels)) {
    if (liveScores[col] != null) {
      scoreRows.push([label, liveScores[col]]);
    }
  }

  // Detail rows
  const detailRows = [];
  if (fields.area != null) {
    detailRows.push([t("area"), formatArea(fields.area)]);
  }
  const detailLabels = {
    road_distance_m: t("road_distance"),
    building_density: t("building_density"),
    industrial_distance_m: t("industrial_distance"),
    residential_distance_m: t("residential_distance"),
    fish_species_count: t("fish_species"),
  };
  for (const [col, label] of Object.entries(detailLabels)) {
    if (fields[col] != null) {
      const val = col.endsWith("_m") ? formatDist(fields[col]) : fields[col];
      detailRows.push([label, val]);
    }
  }

  // Prized genera present at this lake
  if (cfg && fields.fish_genera_mask != null) {
    const fishingGenera = cfg.scoring?.fishing?.genera ?? [];
    const present = fishingGenera
      .filter(g => (fields.fish_genera_mask & (1 << g.code)) !== 0)
      .map(g => t(`genus_${g.genus}`) || g.label);
    if (present.length > 0) {
      detailRows.push([t("prized_fish"), present.join(", ")]);
    }
  }

  let html = "<div class='tt-popup'>";

  // Lake name headline (only when present and non-null)
  if (fields.name) {
    html += `<div class='tt-popup-name'>${fields.name}</div>`;
    html += "<hr class='tt-popup-divider'>";
  }

  // Overall score is the first table row (see below)

  html += "<table>";
  if (liveScores.tentability_score != null) {
    html += `<tr><th class="tt-popup-overall-label">${t("overall_score")}</th><td>${badge(liveScores.tentability_score)}</td></tr>`;
    html += "<tr><td colspan='2'><hr></td></tr>";
  }
  for (const [label, val] of scoreRows) {
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
        color: feature.properties?.color ?? "#999999",
        weight: 2,
        opacity: 0.8,
      }),
    }).addTo(map);
  }

  // Lakes
  const fields = data.lake_fields;
  const idx = {};
  for (let i = 0; i < fields.length; i++) idx[fields[i]] = i;

  lakesLayer = L.markerClusterGroup({
    disableClusteringAtZoom: 10,
    maxClusterRadius: 120,
    spiderfyOnMaxZoom: false,
    zoomToBoundsOnClick: true,
    chunkedLoading: true,
  }).addTo(map);
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
  buildLegend();
  buildFooter();

  // Initial filter pass
  setTimeout(() => teltturUpdate(data.config, idx), 100);
}

// ---------------------------------------------------------------------------
// Controls panel
// ---------------------------------------------------------------------------

/** Toggle a scoring dimension card body on/off and trigger a map update. */
function ttToggleDim(id) {
  const cb = document.getElementById(id);
  const cardBody = document.getElementById(id + "-body");
  if (cardBody) cardBody.style.display = (cb && cb.checked) ? "" : "none";
  teltturUpdate(_ttCfg);
}

/**
 * Build a scoring dimension card element.
 * @param {string} id            - Checkbox element id (e.g. "tt-cabin").
 * @param {string} label         - Display label.
 * @param {string} infoText      - Tooltip description text.
 * @param {string} bodyHtml      - Inner HTML for the card body (sliders etc.).
 * @param {boolean} defaultChecked - Whether the dimension starts enabled.
 */
function buildDimCard(id, label, infoText, bodyHtml, defaultChecked = true) {
  const card = document.createElement("div");
  card.className = "tt-dim-card";
  card.innerHTML =
    `<div class="tt-dim-header">` +
    `<label><input type="checkbox" id="${id}"${defaultChecked ? " checked" : ""}> ${label}</label>` +
    `<span class="tt-info-btn" tabindex="0">ⓘ` +
    `<span class="tt-info-tip">${infoText}</span>` +
    `</span>` +
    `</div>` +
    bodyHtml;
  if (!defaultChecked) {
    const cardBody = card.querySelector(`#${id}-body`);
    if (cardBody) cardBody.style.display = "none";
  }
  card.querySelector(`#${id}`).addEventListener("change", () => ttToggleDim(id));
  card.querySelector(".tt-info-btn").addEventListener("click", function () {
    this.classList.toggle("tt-info-open");
  });
  return card;
}

function buildControls(cfg, lakeFields) {
  const ctrl = cfg.interactive;
  const scoring = cfg.scoring || {};
  const lakeFieldSet = new Set(lakeFields);

  const container = document.createElement("div");
  container.id = "tt-controls";

  // Header
  const header = document.createElement("div");
  header.id = "tt-controls-header";
  header.innerHTML =
    `<b>⚙ ${t("scoring")}</b>` +
    `<button id="tt-toggle-btn">▼</button>`;
  container.appendChild(header);

  const body = document.createElement("div");
  body.id = "tt-body";
  container.appendChild(body);

  header.querySelector("#tt-toggle-btn").addEventListener("click", () => {
    body.style.display = body.style.display === "none" ? "block" : "none";
  });

  // Accessibility card
  {
    const ar = ctrl.accessibility_range;
    let bodyHtml = "";
    if (lakeFieldSet.has("road_distance_m")) {
      const arMin = ar.min_m | 0;
      const arMax = ar.max_m | 0;
      bodyHtml =
        `<div class="tt-dim-body" id="tt-access-body">` +
        `<div id="tt-ar-range-label" style="margin-bottom:6px">` +
        `${t("road_distance")}: ` +
        `<span id="tt-ar-min-val" style="font-weight:bold">${arMin}</span> m` +
        ` – ` +
        `<span id="tt-ar-max-val" style="font-weight:bold">${arMax}</span> m` +
        `</div>` +
        `<div id="tt-ar-slider"></div>` +
        `</div>`;
    }
    body.appendChild(buildDimCard(
      "tt-access", t("accessibility"),
      t("accessibility_info"),
      bodyHtml,
    ));
  }

  // Land use (AR5) card
  {
    const ar5s = scoring.ar5_land_use;
    let bodyHtml = "";
    if (ar5s && lakeFieldSet.has("industrial_distance_m")) {
      const resVal = ar5s.residential_buffer_m | 0;
      const indVal = ar5s.industrial_buffer_m | 0;
      bodyHtml =
        `<div class="tt-dim-body" id="tt-ar5-body">` +
        `${t("ar5_residential")} <span id="tt-ar5-res-val" style="font-weight:bold">${resVal}</span> m<br>` +
        `<div id="tt-ar5-res-slider"></div>` +
        `${t("ar5_industrial")} <span id="tt-ar5-ind-val" style="font-weight:bold">${indVal}</span> m<br>` +
        `<div id="tt-ar5-ind-slider"></div>` +
        `</div>`;
    }
    body.appendChild(buildDimCard(
      "tt-ar5", t("ar5_land_use"),
      t("ar5_land_use_info"),
      bodyHtml,
    ));
  }

  // Buildings (cabin density) card — starts unchecked
  {
    const cd = ctrl.cabin_density_slider;
    let bodyHtml = "";
    if (lakeFieldSet.has("building_density")) {
      const defaultLabel = (t("cabin_density_levels") ?? [])[cd.default_step - 1] ?? cd.default_step;
      bodyHtml =
        `<div class="tt-dim-body" id="tt-cabin-body">` +
        `${t("cabin_density_tolerance")} <span id="tt-ct-val" style="font-weight:bold">${defaultLabel}</span>` +
        `<div class="tt-slider-range-labels">` +
        `<span>${t("cabin_density_level_low")}</span><span>${t("cabin_density_level_high")}</span>` +
        `</div>` +
        `<div id="tt-ct-slider"></div>` +
        `</div>`;
    }
    body.appendChild(buildDimCard(
      "tt-cabin", t("cabin_density"),
      t("cabin_density_info"),
      bodyHtml,
      false,
    ));
  }

  // Fishing card — starts unchecked
  {
    const fishingGenera = scoring.fishing?.genera ?? [];
    let bodyHtml = "";
    if (fishingGenera.length > 0 && lakeFieldSet.has("fish_genera_mask")) {
      bodyHtml =
        `<div class="tt-dim-body" id="tt-fishing-body">` +
        `<div class="tt-fish-dropdown">` +
        `<button class="tt-fish-btn" id="tt-fish-btn" type="button">` +
        `<span id="tt-fish-summary">${t("fish_selected_all")}</span>` +
        `<span class="tt-fish-arrow">▾</span>` +
        `</button>` +
        `<div class="tt-fish-panel" id="tt-fish-panel" hidden>` +
        `<button class="tt-fish-toggle-all" id="tt-fish-toggle-all" type="button">${t("fish_deselect_all")}</button>` +
        fishingGenera.map(g =>
          `<label><input type="checkbox" id="tt-fg-${g.code}" checked> ${t(`genus_${g.genus}`) || g.label}</label>`
        ).join("") +
        `</div>` +
        `</div>` +
        `</div>`;
    }
    body.appendChild(buildDimCard(
      "tt-fishing", t("fishing"),
      t("fishing_info"),
      bodyHtml,
      false,
    ));
  }

  // Lake size filter — separate section at the bottom
  {
    const filterDiv = document.createElement("div");
    filterDiv.className = "tt-filter-section";
    filterDiv.innerHTML =
      `<div class="tt-filter-header">${t("lake_size_filter")}</div>` +
      `<div class="tt-filter-hint">${t("lake_size_filter_hint")}</div>` +
      `<div id="tt-ls-range-label" style="margin-bottom:2px">` +
      `<span id="tt-ls-min-val" style="font-weight:bold">${formatArea(0)}</span>` +
      ` – ` +
      `<span id="tt-ls-max-val" style="font-weight:bold">${formatArea(50000000)}</span>` +
      `</div>` +
      `<div id="tt-ls-slider"></div>`;
    body.appendChild(filterDiv);
  }

  document.body.appendChild(container);

  // Initialise noUiSlider for cabin density (discrete steps mapped to quantiles)
  const ctSliderEl = document.getElementById("tt-ct-slider");
  if (ctSliderEl && typeof noUiSlider !== "undefined") {
    const cd = ctrl.cabin_density_slider;
    const levels = t("cabin_density_levels") ?? [];
    _ctSlider = noUiSlider.create(ctSliderEl, {
      start: [cd.default_step],
      connect: [true, false],
      step: 1,
      range: { min: 1, max: cd.steps },
    });
    _ctSlider.on("update", (values) => {
      const step = Math.round(parseFloat(values[0]));
      const label = levels[step - 1] ?? step;
      document.getElementById("tt-ct-val").textContent = label;
    });
    _ctSlider.on("change", () => teltturUpdate(_ttCfg));
  }

  // Initialise noUiSlider for AR5 residential buffer
  const ar5ResSliderEl = document.getElementById("tt-ar5-res-slider");
  if (ar5ResSliderEl && typeof noUiSlider !== "undefined") {
    const ar5b = ctrl.ar5_buffers;
    const ar5s = scoring.ar5_land_use;
    _ar5ResSlider = noUiSlider.create(ar5ResSliderEl, {
      start: [ar5s.residential_buffer_m | 0],
      connect: [true, false],
      step: 100,
      range: { min: 0, max: ar5b.slider_max_m | 0 },
    });
    _ar5ResSlider.on("update", (values) => {
      document.getElementById("tt-ar5-res-val").textContent = Math.round(values[0]);
    });
    _ar5ResSlider.on("change", () => teltturUpdate(_ttCfg));
  }

  // Initialise noUiSlider for AR5 industrial buffer
  const ar5IndSliderEl = document.getElementById("tt-ar5-ind-slider");
  if (ar5IndSliderEl && typeof noUiSlider !== "undefined") {
    const ar5b = ctrl.ar5_buffers;
    const ar5s = scoring.ar5_land_use;
    _ar5IndSlider = noUiSlider.create(ar5IndSliderEl, {
      start: [ar5s.industrial_buffer_m | 0],
      connect: [true, false],
      step: 100,
      range: { min: 0, max: ar5b.slider_max_m | 0 },
    });
    _ar5IndSlider.on("update", (values) => {
      document.getElementById("tt-ar5-ind-val").textContent = Math.round(values[0]);
    });
    _ar5IndSlider.on("change", () => teltturUpdate(_ttCfg));
  }

  // Fish genera dropdown events
  const fishingGeneraArr = scoring.fishing?.genera ?? [];
  const fishBtnEl = document.getElementById("tt-fish-btn");
  const fishPanelEl = document.getElementById("tt-fish-panel");
  const fishToggleEl = document.getElementById("tt-fish-toggle-all");

  function _updateFishSummary() {
    let sel = 0;
    for (const g of fishingGeneraArr) {
      if (checkVal(`tt-fg-${g.code}`, true)) sel++;
    }
    const sumEl = document.getElementById("tt-fish-summary");
    if (sumEl) {
      if (sel === fishingGeneraArr.length) sumEl.textContent = t("fish_selected_all");
      else if (sel === 0) sumEl.textContent = t("fish_selected_none");
      else sumEl.textContent = `${sel} / ${fishingGeneraArr.length}`;
    }
    if (fishToggleEl) {
      fishToggleEl.textContent = sel === fishingGeneraArr.length ? t("fish_deselect_all") : t("fish_select_all");
    }
  }

  if (fishBtnEl && fishPanelEl) {
    fishBtnEl.addEventListener("click", () => {
      const nowHidden = !fishPanelEl.hidden;
      fishPanelEl.hidden = nowHidden;
      fishBtnEl.closest(".tt-fish-dropdown").classList.toggle("open", !nowHidden);
    });
  }

  if (fishToggleEl) {
    fishToggleEl.addEventListener("click", () => {
      const anyUnchecked = fishingGeneraArr.some(g => !checkVal(`tt-fg-${g.code}`, true));
      for (const g of fishingGeneraArr) {
        const cb = document.getElementById(`tt-fg-${g.code}`);
        if (cb) cb.checked = anyUnchecked;
      }
      _updateFishSummary();
      teltturUpdate(_ttCfg);
    });
  }

  for (const g of fishingGeneraArr) {
    const cb = document.getElementById(`tt-fg-${g.code}`);
    if (cb) {
      cb.addEventListener("change", () => {
        _updateFishSummary();
        teltturUpdate(_ttCfg);
      });
    }
  }

  // Initialise noUiSlider for accessibility range
  const arSliderEl = document.getElementById("tt-ar-slider");
  if (arSliderEl && typeof noUiSlider !== "undefined") {
    const ar = ctrl.accessibility_range;
    _arSlider = noUiSlider.create(arSliderEl, {
      start: [ar.min_m | 0, ar.max_m | 0],
      connect: true,
      step: 100,
      range: { min: 0, max: ar.slider_max_m | 0 },
    });
    _arSlider.on("update", (values) => {
      document.getElementById("tt-ar-min-val").textContent = Math.round(values[0]);
      document.getElementById("tt-ar-max-val").textContent = Math.round(values[1]);
    });
    _arSlider.on("change", () => teltturUpdate(_ttCfg));
  }

  // Initialise noUiSlider for lake size range
  const lsSliderEl = document.getElementById("tt-ls-slider");
  if (lsSliderEl && typeof noUiSlider !== "undefined") {
    _lakeSizeSlider = noUiSlider.create(lsSliderEl, {
      start: [0, 50000000],
      connect: true,
      range: {
        "min": [0, 100],
        "15%": [1000, 500],
        "35%": [10000, 2500],
        "55%": [100000, 25000],
        "70%": [1000000, 250000],
        "85%": [10000000, 5000000],
        "max": [50000000],
      },
    });
    _lakeSizeSlider.on("update", (values) => {
      document.getElementById("tt-ls-min-val").textContent = formatArea(parseFloat(values[0]));
      document.getElementById("tt-ls-max-val").textContent = formatArea(parseFloat(values[1]));
    });
    _lakeSizeSlider.on("change", () => teltturUpdate(_ttCfg));
  }
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function buildLegend() {
  const legend = document.createElement("div");
  legend.id = "tt-legend";
  let html = `<div class="tt-legend-header">${t("legend_suitability")}</div>`;
  for (let level = 5; level >= 1; level--) {
    html +=
      `<div class="tt-legend-row">` +
      `<span class="tt-legend-swatch" style="background:${LEVEL_COLORS[level]}"></span>` +
      `${t(`level_${level}`)}</div>`;
  }
  legend.innerHTML = html;
  document.body.appendChild(legend);
}

// ---------------------------------------------------------------------------
// Footer bar + credits dialog
// ---------------------------------------------------------------------------

function buildFooter() {
  const footer = document.createElement("div");
  footer.id = "tt-footer";
  footer.innerHTML =
    `<a href="https://github.com/vegardkv/telttur" target="_blank" rel="noopener">GitHub</a>` +
    `<span class="tt-footer-sep">·</span>` +
    `<button id="tt-credits-btn">${t("credits")}</button>`;
  document.body.appendChild(footer);

  const dialog = document.createElement("dialog");
  dialog.id = "tt-credits-dialog";
  dialog.innerHTML =
    `<div class="tt-credits-body">` +
    `<b>${t("credits_data")}</b>` +
    `<ul>` +
    `<li><a href="https://kartkatalog.geonorge.no/metadata/n50-kartdata/ea192681-d039-42ec-b1bc-f3ce04c189ac" target="_blank" rel="noopener">Kartverket</a> — ${t("credits_n50")}</li>` +
    `<li><a href="https://www.nibio.no/tema/jord/arealressurser/arealressurskart-ar5" target="_blank" rel="noopener">NIBIO</a> — ${t("credits_ar5")}</li>` +
    `<li><a href="https://ipt.nina.no/resource?r=vanninfofisk" target="_blank" rel="noopener">NINA</a> — ${t("credits_nina")}</li>` +
    `<li><a href="https://www.kartverket.no/" target="_blank" rel="noopener">Kartverket</a> — ${t("credits_basemap")}</li>` +
    `</ul>` +
    `<b>${t("credits_library")}</b>` +
    `<ul><li><a href="https://leafletjs.com/" target="_blank" rel="noopener">Leaflet</a></li></ul>` +
    `<b>${t("credits_source_code")}</b>` +
    `<ul><li><a href="https://github.com/vegardkv/telttur" target="_blank" rel="noopener">github.com/vegardkv/telttur</a></li></ul>` +
    `</div>` +
    `<button class="tt-credits-close">✕</button>`;
  footer.querySelector("#tt-credits-btn").addEventListener("click", () => dialog.showModal());
  dialog.querySelector(".tt-credits-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  document.body.appendChild(dialog);
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

let _ttCfg = null;
let _ttData = null;

function _start(data) {
  _ttCfg = data.config;
  _ttData = data;
  document.title = t("title");
  initMap(data);
}

if (window.TELTTUR_DATA) {
  _start(window.TELTTUR_DATA);
} else {
  document.body.innerHTML =
    `<div style="padding:2em;font-family:sans-serif;color:#c00">` +
    `<h2>${t("error_no_data")}</h2>` +
    `</div>`;
}
