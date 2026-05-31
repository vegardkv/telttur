# Task 38 – Marker clustering for zoom performance

Zooming the full-country map is sluggish because Leaflet reprojects and
redraws every `CircleMarker` on every zoom frame. The fix is
`L.markerClusterGroup` from Leaflet.markercluster: it replaces groups of
nearby markers with a single cluster icon at low zoom, so the canvas only
redraws a handful of objects at country/regional scale. Individual markers
appear as normal once zoomed past a configurable threshold.

The per-marker API (`bindPopup`, `setStyle`, `addTo`) is fully preserved —
`teltturUpdate()`, popup logic, and scoring are untouched.

Scope: `web/index.html` (add CDN tags) and `web/app.js` (~5 line change).

---

## 1. Add Leaflet.markercluster via CDN

In `web/index.html`, after the Leaflet `<link>` and `<script>` tags, add:

```html
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" crossorigin="">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" crossorigin="">
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js" crossorigin=""></script>
```

The Default CSS provides the built-in cluster icon styles that we will
override in step 3.

---

## 2. Replace `L.layerGroup` with `L.markerClusterGroup`

In `initMap` (`app.js:448`), replace:

```js
lakesLayer = L.layerGroup().addTo(map);
```

with:

```js
lakesLayer = L.markerClusterGroup({
  disableClusteringAtZoom: 11,
  maxClusterRadius: 60,
  spiderfyOnMaxZoom: false,
  zoomToBoundsOnClick: true,
  chunkedLoading: true,
  iconCreateFunction: () => clusterIcon,
}).addTo(map);
```

**Option notes:**
- `disableClusteringAtZoom: 11` — at zoom ≥ 11 (roughly municipality level)
  individual lake dots appear as today. Tune this value based on feel.
- `maxClusterRadius: 60` — controls how aggressively nearby markers are
  merged. Lower = tighter clusters, more icons. Tune as needed.
- `spiderfyOnMaxZoom: false` — we don't use pin markers; spiderfy is only
  useful for stacked pins.
- `zoomToBoundsOnClick: true` — clicking a cluster zooms to its extent,
  which is natural navigation for this map.
- `chunkedLoading: true` — adds markers to the cluster group in chunks so
  the initial load doesn't block the UI thread on large datasets.
- `iconCreateFunction` — omit; use the default Leaflet.markercluster icon.

Everything else — `marker.addTo(lakesLayer)`, `marker.setStyle(...)`,
`marker.bindPopup(...)`, `marker.on("popupopen", ...)` — is unchanged.

---

## 3. Cluster icon

Use the default Leaflet.markercluster icon. No `iconCreateFunction`, no
custom CSS. The default shows a count badge and varies size/colour by
cluster density — sufficient for indicating lake concentration without any
custom work.

---

## 4. Verification

Manual, in browser, using the full-country config:

- [ ] At country zoom (≤ 10): cluster circles appear and the map pans and
      zooms smoothly without sluggishness.
- [ ] Clicking a cluster zooms to its extent.
- [ ] At zoom ≥ 11: individual lake dots appear, coloured by score as today.
- [ ] Popups still open with correct content when clicking individual dots.
- [ ] All controls still work: lake-size slider, accessibility range, AR5
      buffers, cabin tolerance, fishing genera — each recolours/hides markers,
      and cluster icons update accordingly when zooming back out.
- [ ] No console errors during zoom, pan, filter changes, or clicks.
- [ ] Cluster icon is the default markercluster style (count badge, density colouring).
- [ ] The transition from cluster → individual dots at zoom 11 feels natural;
      adjust `disableClusteringAtZoom` or `maxClusterRadius` if it does not.

---

## Out of scope

- Custom cluster icon styling — the default markercluster icon is used as-is.
- Spiderfying — not applicable to circle markers.
- Vendoring markercluster locally — the project already relies on CDN for
  Leaflet and noUiSlider, so adding a third CDN tag is consistent.
- The task-36 "cheap wins" (remove filtered markers, zoom decimation, single
  renderer) — those have been reverted; clustering supersedes them.

---

## Outcome (2026-05-31): Adopted

This is the way forward for now. Clustering worked well and load time was
brought back under control once markers were bulk-inserted via
`addLayers()` instead of one-at-a-time `addTo()` (the latter rebuilds the
cluster tree on every insert, which dominated initial load with ~142k lakes).
Markers are also coloured at creation from the initial control state, removing
the redundant post-load re-style pass.

If clustering proves dissatisfactory in the future, the best path forward is
likely to **swap Leaflet for something more performant** for a dataset of this
size, rather than continue layering optimisations onto Leaflet.
