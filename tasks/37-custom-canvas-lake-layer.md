# Task 37 – Custom canvas lake layer (with spatial-index popups)

Task 36's cheap wins (remove filtered markers from the layer, zoom-based area
decimation, single canvas renderer) were not enough: zooming the full-country
map is still sluggish. The remaining bottleneck is `L.circleMarker` itself —
one Leaflet object per lake, each reprojected and redrawn on every zoom frame.
At tens of thousands of lakes the per-object overhead dominates.

This task replaces the per-lake `CircleMarker` objects with a **single custom
canvas layer** that draws all visible lakes in one pass, plus a lightweight
**spatial index** so clicks still resolve to the right lake and the existing
popups keep working unchanged.

Scope: `web/app.js` only. No Python changes. No new runtime dependency (the
spatial index is a small inline grid — see §3).

---

## Why this keeps popups working (the key constraint)

The popup *content* pipeline does not change at all:
`readControlState()`, `computeScores()`, and `buildPopup()` stay exactly as
they are today. What changes is only how a click is mapped to a lake.

- **Today:** Leaflet owns a `CircleMarker` per lake; it does hit-testing and
  fires `popupopen`, where we call `buildPopup(f, computeScores(f, cs), cfg)`
  (`app.js:472–474`).
- **After:** there are no per-lake objects. We listen for `map.on("click")`,
  use the spatial index to find the nearest visible lake within the dot
  radius, and open a single shared popup at that lake with the *same*
  `buildPopup(...)` content.

Net effect for the user: clicking a dot still opens the identical popup.

---

## 1. The custom canvas layer

Create a custom layer that draws every currently-visible lake as a filled
circle directly onto a canvas, in one redraw per zoom/pan — instead of N
Leaflet objects.

Two acceptable implementations; pick whichever is cleaner in practice:

**Option A — `L.Canvas` with manual paths (simplest, recommended first).**
Keep using Leaflet's canvas renderer but stop creating N markers. Instead
subclass `L.Layer` and in `onAdd` grab the renderer's 2D context; on
`redraw` (wired to `map` `zoomend`/`moveend`/`viewreset`) iterate the visible
lakes and draw each with `ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 2π);
ctx.fillStyle = color; ctx.fill()` where `p = map.latLngToContainerPoint(...)`.

**Option B — hand-rolled `<canvas>` overlay layer.** A custom `L.Layer`
that owns its own `<canvas>` positioned over the map pane, repositioned on
`move` and fully repainted on `zoomend`/`moveend`. More control, slightly
more boilerplate. Use only if Option A's interaction with Leaflet's renderer
gets awkward.

**Drawing rules (match current visuals):**
- Radius: `8` px (same as today's `radius: 8`), constant in screen space.
- Fill: `LEVEL_COLORS[score]` (or `DEFAULT_LAKE_COLOR` when no score).
- Stroke: `#333333`, `lineWidth` ~`0.8` — but per-dot stroking is the most
  expensive part. If stroking all dots is slow, batch fills by colour
  (group lakes by `fillStyle`, one `beginPath` per colour, all arcs, one
  `fill`) and consider dropping the stroke at far zoom levels.
- Only draw lakes that pass the current filter **and** the zoom-area
  decimation from task 36 §2 **and** intersect the padded viewport bounds
  (see §3 culling).

**Replaces:**
- The `L.circleMarker(...)` creation loop in `initMap` (`app.js:451–478`).
- The per-marker styling in `teltturUpdate` (`app.js:313–330`) — now a
  single `layer.redraw()` call after recomputing which lakes are visible.

**Keep:** `allMarkers` becomes a plain array of lake records
`{ lat, lng, fields, score, visible }` (rename to e.g. `allLakes` — it no
longer holds Leaflet markers). It stays the source of truth for the full set.

---

## 2. Recompute pipeline

`teltturUpdate(cfg)` no longer touches Leaflet objects. It should:

1. Read control state once: `const cs = readControlState(cfg)`.
2. Compute `zoomMinArea` from `map.getZoom()` (task 36 §2 table).
3. For each lake record: determine `visible` (area filter ∩ zoom decimation)
   and, if visible, `score = computeScores(fields, cs).tentability_score`.
4. Call `lakeLayer.redraw()`.

The actual viewport culling happens inside the layer's draw (only draw lakes
whose projected point falls within the padded canvas bounds), so
`teltturUpdate` stays O(N) only over the filter math, and the draw loop is
O(visible-in-viewport).

Wire redraw triggers:
- `map.on("zoomend moveend", () => teltturUpdate(_ttCfg))` (replaces the
  task-36 `zoomend` handler; `moveend` is now needed for viewport culling).
- All existing slider/checkbox `change` handlers already call
  `teltturUpdate(_ttCfg)` — unchanged.

---

## 3. Spatial index + click → popup

Add a lightweight **uniform grid index** over lake coordinates. No external
dependency: a `Map` keyed by `"col:row"` cells (cell size ≈ a few hundred
metres in lat/lng) whose values are arrays of lake-record indices. This fits
the project's "lightweight, no build step, file:// safe" constraints better
than vendoring KDBush as a global.

```js
// Build once after lakes are loaded:
const CELL = 0.02; // ~tunable: degrees; ~2 km lat. Smaller = faster queries.
const grid = new Map();
const key = (lat, lng) => `${Math.floor(lng / CELL)}:${Math.floor(lat / CELL)}`;
allLakes.forEach((l, i) => {
  const k = key(l.lat, l.lng);
  (grid.get(k) ?? grid.set(k, []).get(k)).push(i);
});
```

**Click handling — single shared popup:**

```js
const sharedPopup = L.popup({ maxWidth: 300 });

map.on("click", (e) => {
  const hit = nearestVisibleLake(e.latlng, e.containerPoint);
  if (!hit) return;                      // clicked empty space → ignore
  const cs = readControlState(_ttCfg);
  sharedPopup
    .setLatLng([hit.lat, hit.lng])
    .setContent(buildPopup(hit.fields, computeScores(hit.fields, cs), _ttCfg))
    .openOn(map);
});
```

**`nearestVisibleLake(latlng, clickPt)`:**
1. Look up the click's grid cell plus its 8 neighbours → candidate indices.
2. Filter to `visible` lakes only.
3. Convert each candidate's `latlng` to a container point and compute pixel
   distance to `clickPt`.
4. Return the closest candidate whose pixel distance ≤ dot radius (`8`) +
   a small slop (e.g. `2`). Confirming the hit in **pixel space** makes it
   match the visible dot size at any zoom, which a pure-degrees radius does
   not.

This makes clicks O(candidates-in-9-cells), independent of total lake count.

**Removes:** `marker.bindPopup("")` and the per-marker `popupopen` handler
(`app.js:471–475`) — replaced by the single `map.on("click")` handler above.

---

## 4. Things to preserve / watch

- **Roads** stay as `L.geoJSON` on the canvas renderer (task 36 §3) — they
  are few and not the bottleneck. Don't fold them into the custom layer.
- **Popup-on-recolour:** if a slider moves while a popup is open, today the
  popup content goes stale (same as current behaviour — it only refreshes on
  open). Keep that behaviour; do not add live popup refresh unless trivial.
- **Hit priority when dots overlap:** nearest-center is the right pick and
  matches user intent. Document it; don't over-engineer.
- **Hover cursor (optional, low priority):** a `mousemove` handler reusing
  `nearestVisibleLake` could set `map.getContainer().style.cursor`. Skip
  unless cheap — `mousemove` fires often and could reintroduce cost.
- **Empty-viewport draw:** guard against drawing when `allLakes` is empty.
- **Retina / devicePixelRatio:** if using Option B's own canvas, scale the
  backing store by `window.devicePixelRatio` so dots aren't blurry. Option A
  inherits Leaflet's handling for free — another reason to prefer it.

---

## 5. Verification

Manual, in browser, with the full-country config that exhibits the lag:

- [ ] Zoom in/out at country, regional, and local extents — should be
      dramatically smoother than the task-36 state (the whole point).
- [ ] Pan at country zoom — smooth; dots near the edge appear without gaps
      (viewport padding works).
- [ ] **Click a dot → the correct popup opens with correct scores.** Click
      empty space → nothing opens. Click near two overlapping dots → the
      nearer one opens.
- [ ] Every control still works: lake-size slider, accessibility range, AR5
      buffers, cabin tolerance, fishing genera — each recolours/hides dots.
- [ ] Colours match the old `CircleMarker` rendering (spot-check a few known
      lakes against `main`).
- [ ] Roads still render unchanged.
- [ ] No console errors during zoom, pan, filter changes, or clicks.
- [ ] Single-file embed (`config` with embed option) still opens via
      `file://` with no network and popups still work — confirms no ES-module
      / external-dep regression.

No automated tests (vanilla JS, no harness). `uv run ruff check` / `uv run ty
check` unaffected (Python untouched).

---

## 6. If this is still not enough

Escalation path, in order:
- **Batch fills by colour** (if not already done) and drop strokes at far
  zoom — biggest remaining canvas-draw win.
- **Swap the inline grid for KDBush + geokdbush** only if click latency
  becomes an issue (it should not at this point).
- **Vector tiles / PMTiles** — last resort, large architectural change, and
  it complicates the `file://` single-file embed story. Out of scope here.

---

## Outcome (2026-05-31): Not adopted

This approach was prototyped and **disregarded**. The custom canvas layer did
not feel right in use, and it noticeably hurt the readability of `app.js`. The
added complexity wasn't worth the trade-off, so it was dropped in favour of the
Leaflet.markercluster approach in task 38.
