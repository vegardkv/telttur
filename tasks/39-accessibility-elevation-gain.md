# Task 39 – Elevation gain in accessibility

Round 10 item: *"Add difference in vertical meters to accessibility. Perhaps even
evaluate the straight line between nearest point and lake."*

## Objective

Accessibility currently scores a lake purely by the **horizontal** Euclidean distance
to the nearest drivable road (`road_distance_m`, computed in
`src/telttur/scoring/accessibility.py` via `sjoin_nearest`). A 1 km walk that climbs
400 m is a very different hike from 1 km on the flat. Factor the **vertical climb**
between the nearest road point and the lake into the accessibility dimension.

## Context / current state

- `score_accessibility()` adds only `road_distance_m`. `sjoin_nearest` gives the
  distance and the matched road row, but we currently discard the nearest *point* on
  the road — we only keep the min distance per lake.
- There is **no elevation/DEM data anywhere in the pipeline today** (confirmed: no
  `elevation`/`dem`/`moh` references in `src/`). This task introduces it.
- The frontend re-scores live in `web/app.js` → `scoreAccess(dist, minM, maxM)`
  (lines ~187). Whatever new field we export must be consumed there.

## How climb affects the score (decided)

A **dedicated climb slider** in the accessibility card. Horizontal `road_distance_m`
keeps feeding `scoreAccess` unchanged; climb is scored independently and combined into
the accessibility score via `Math.min(...)`, consistent with how the other dimensions
compose their sub-scores.

- The slider sets a **max acceptable climb** (metres). Within it → Utmerket (5);
  beyond it the score tapers to Elendig (1) following the same taper shape as the
  other dimensions (round 9 — consistent taper to Elendig).
- Use the **absolute** vertical difference for scoring (a steep descent to the lake is
  also effort/exposure); keep the signed value for the popup display.
- The accessibility score becomes
  `Math.min(scoreAccess(dist, arMin, arMax), scoreClimb(|gain|, maxClimb))`.

## DEM data source

Elevation comes from a Geonorge DTM (digital terrain model):

- **Dataset**: "Digital terrengmodell 10 m" (DTM10) or DTM50, Kartverket, CC BY 4.0 —
  same licensing family as the existing N50 sources.
- Fetch as a GeoTIFF and sample it with `rasterio` (new dependency — add via
  `uv add rasterio`). Sampling N points is a `list(src.sample(coords))` call.
- Cache the raster under the existing download/data dir, mirroring
  `_ensure_nina_archive` in `fishing.py` (download-if-absent, reuse cache).
- A coarse DTM (50 m) is plenty for a climb estimate and keeps the download small;
  start there and revisit resolution only if needed.

## Steps

1. **Download/cache the DEM** — new module `src/telttur/elevation.py` (or extend
   `download.py`) with an `_ensure_dem(...)`-style helper returning a raster path.
   Follow the cache pattern in `fishing.py`.

2. **Capture the nearest road point** in `score_accessibility()`:
   - Use `shapely.ops.nearest_points(lake_geom, nearest_road_geom)` for the lake/road
     pair that `sjoin_nearest` selected, to get the actual road point (not just the
     distance). Keep working in `CRS_UTM33`.

3. **Sample elevations** for the lake representative point and the nearest road point;
   compute `elevation_gain_m = round(lake_elev - road_elev, 1)` (signed — uphill from
   road to lake is positive). Add a `LakeCols.ELEVATION_GAIN_M` column (and, for
   approach 1, optionally a precomputed `slope_distance_m`).

4. **Export** the new column — add `LakeCols.ELEVATION_GAIN_M` to `optional_cols` in
   `build_lake_data()` (`data_export.py`); it flows through automatically. (No
   `slope_distance_m` needed — the climb slider scores the gain directly.)

5. **Config for the slider** — add a model for the climb slider bound under
   `InteractiveControlsConfig` (`config.py`, near `accessibility_range` at ~line 79),
   e.g. `InteractiveClimb(max_m: float = 200.0, slider_max_m: float = 1000.0)`, and
   surface it in `build_config_block()`'s `interactive_cfg` (`data_export.py`, ~163)
   so the frontend reads its defaults like the other sliders.

6. **Frontend** (`web/app.js`):
   - Add a `scoreClimb(gain, maxClimb)` helper following the existing taper shape
     (see `scoreAr5One` / `scoreAccess`, ~187–221): 5 within `maxClimb`, tapering to 1.
   - Add a climb slider to the **accessibility card** (`buildControls`, ~620s) wired
     like the other noUiSliders — label updates on `update`, re-score on `change`
     (task 34 split-handler pattern). Read its value in `readControlState` (~254) as
     `cs.climbMax`.
   - In `computeScores` (~298), combine:
     `live.accessibility_score = Math.min(scoreAccess(road_distance_m, arMin, arMax), scoreClimb(Math.abs(elevation_gain_m), cs.climbMax))`.
     Guard for `elevation_gain_m == null` (fall back to distance-only).
   - Show "Stigning: ±N m" in the popup (add a label + i18n key alongside
     `road_distance` near lines 38 / 386 / 607).

7. **Docs**: update `CLAUDE.md` (Data Sources table → add DTM/Kartverket; Scoring
   Dimensions → note accessibility now considers climb), the accessibility info
   tooltip text in `app.js`, and `tasks/29-attributions-and-licensing.md` if the
   attribution list is maintained there.

## Acceptance criteria

- [ ] DEM is downloaded once and cached; re-runs reuse the cache.
- [ ] Each lake has a signed `elevation_gain_m` relative to its nearest road point.
- [ ] Accessibility card has a max-climb slider; it tapers the accessibility score
      (combined via `Math.min` with the distance score) and re-colours on release.
- [ ] Popup shows the vertical difference in metres.
- [ ] `uv run ruff check`, `uv run ruff format`, `uv run ty check` all pass.
- [ ] Docs and in-app accessibility description updated.
