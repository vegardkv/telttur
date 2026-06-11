# Task 43: Frontend Load Performance — Main-Thread Cost

## Objective
Reduce the work the browser does on the main thread during initial load. After
task (FCP fix) the basemap paints fast, but parsing the dataset and building all
lake markers still blocks the main thread for several seconds.

## Background

The FCP fix decoupled the basemap render from the data download: `initShell()`
paints the map immediately, then `app.js` injects `data.js` and `populate()`s
the lakes once it lands (see the bootstrap section in `web/app.js`).

That fixed **First Contentful Paint** (now ~1.7 s) but left two metrics red on
PageSpeed (mobile):

| Metric | Value | Cause |
|--------|-------|-------|
| Total Blocking Time | ~3.9 s | One long synchronous task: object-literal parse + 125k marker build |
| Speed Index | ~6.9 s | Page stays "loading" until the lakes finish rendering |
| Largest Contentful Paint | ~2.9 s | Basemap tiles / control panel |

Two distinct costs dominate the long task:

1. **Parsing the payload.** `data.js` is `window.TELTTUR_DATA = { ... }` — a
   ~10 MB **JavaScript object literal**, which the engine parses with the full
   JS parser. For large data this is meaningfully slower than `JSON.parse()` of
   an equivalent string (V8 has a fast path for `JSON.parse`).
2. **Building markers.** `populate()` in `web/app.js` loops over ~125k lake rows
   and, for each, builds a field dict, runs `computeScores()`, and constructs an
   `L.circleMarker`, then bulk-inserts via `lakesLayer.addLayers()`. The loop is
   synchronous — one uninterrupted task that blocks input the whole time (TBT
   counts everything past 50 ms of a task).

The payload is also simply large: ~10 MB raw, ~3.7 MB gzipped, mostly numeric.

## Suggested Improvements

Independent; ordered roughly by value-for-effort.

### 1. Shrink the payload (low effort, helps download + parse + memory)
In `src/telttur/data_export.py`:
- Drop coordinate precision from 6 to 5 decimals (`_COORD_PRECISION`, line ~22).
  6 decimals is ~0.1 m — absurd for a lake centroid; 5 is ~1 m.
- Round the distance fields to integers instead of `.1` (the `round(float(val), 1)`
  branch in `build_lake_data`): `road_distance_m`, the two AR5 distances, and
  `elevation_gain_m` don't need decimetre precision.
- Round `area` to an integer.

Smaller text = fewer bytes to download and fewer to parse. Estimate ~10 MB → ~8 MB
raw before compression.

### 2. Emit `JSON.parse('…')` instead of an object literal (low effort, high value)
Change the export so `data.js` is `window.TELTTUR_DATA = JSON.parse('<escaped>');`
rather than assigning a raw object literal (`export_data`, line ~254-257). The
JSON fast path can cut parse time substantially for a payload this size. Mind the
string escaping (quotes, backslashes); generate it from the same `json.dumps`
output, wrapped and escaped for a single-quoted JS string literal.

### 3. Chunk the marker build so it yields to the event loop (medium effort)
Split the `populate()` marker loop into batches (e.g. a few thousand markers per
batch) processed across `requestAnimationFrame`/`setTimeout`/`requestIdleCallback`
ticks. The total work is the same, but no single task exceeds the TBT threshold,
the page stays responsive, and lakes stream in. Keep the existing
`addLayers(markers)` bulk-insert per batch. Watch the loading indicator: only
remove `#tt-loading` after the last batch.

### 4. Preconnect to tile/CDN hosts (low effort, helps LCP)
Add `<link rel="preconnect">` / `dns-prefetch` in `index.html` for
`cache.kartverket.no` (basemap tiles), `unpkg.com`, and `cdn.jsdelivr.net` so the
TLS handshakes overlap with HTML parse. Cheap nudge for LCP/Speed Index.

### 5. Enable Brotli for `data.js` (low effort, host config — no code)
The Pages host already gzips (10 MB → 3.7 MB). Brotli typically gets numeric JSON
~20-25 % smaller still. GitHub Pages serves Brotli for precompressed assets in
some setups; confirm what the host supports. Pure download-time win.

### 6. Viewport / columnar data (higher effort, only if 1-5 aren't enough)
Bigger structural levers if the above don't get TBT green:
- **Columnar typed arrays.** Ship coordinates/fields as binary (e.g.
  base64-encoded `Float32Array`s decoded in JS) instead of array-of-arrays JSON —
  far faster to parse and smaller. Keep base64+inline, not `fetch`, to preserve
  the `file://` dev workflow.
- **Don't build all 125k markers up front.** Build only what the current
  viewport/zoom needs, or lean harder on clustering at low zoom. This is a
  meaningful rework of the lake layer (cf. task 37 canvas layer, task 38
  clustering) — scope carefully.

## Notes / Constraints
- Keep the `file://` dev workflow working (CLAUDE.md): no `fetch()` of local data,
  no ES modules, single-file frontend.
- Measure before/after with PageSpeed (mobile) and the Chrome DevTools Performance
  panel — the long task is easy to see and confirm shrinking.
- Items 1-2 are nearly free and should land first; re-measure before investing in
  3 or 6.

## Acceptance (suggested, scope to chosen items)
- Total Blocking Time materially reduced (target: out of the red band).
- No single main-thread task blocks for multiple seconds during load.
- Payload size and parse time reduced; `file://` and the Pages deploy both still
  work.
