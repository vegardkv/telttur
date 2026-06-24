# Task 45 – Public-transport accessibility (Entur)

## Objective

Accessibility today scores a lake **only by distance to the nearest drivable road**
(`road_distance_m`, computed in `src/telttur/scoring/accessibility.py`, plus a climb
penalty from task 39). But not everyone arrives by car. Add **distance to the nearest
public-transport stop** as a second way a lake can be "accessible", using **Entur** data
(Norway's national public-transport registry), so a car-free user can find lakes they can
actually reach by bus / train / ferry.

New per-lake metric: `transit_distance_m` — metres to the nearest public-transport stop —
scored and folded into the accessibility dimension.

## Background — the hard part is the data (research first)

The pipeline has **no transit data today** (confirmed: no `entur`/`transit`/`gtfs`
references in `src/`). Step one is research: pick an authoritative bulk stop dataset and
decide how to join it to lakes. Don't trust any source below without verifying it.

Entur publishes Norway's national stop and timetable data openly. Candidate sources:

| Source | What it is | Access | Notes |
|--------|-----------|--------|-------|
| **Aggregated national GTFS** (`rb_norway-aggregated-gtfs.zip`) | All routes/stops/timetables for the whole country in one GTFS zip. `stops.txt` = clean CSV of every stop with `stop_id, stop_lat, stop_lon, location_type`. | Single static download (Entur "outbound" GTFS bucket / Entur data portal). | **Recommended for v1** — `stops.txt` is a plain CSV → trivial to load into points. `stop_times.txt`/`trips.txt`/`calendar.txt` are there too if we later want service frequency. |
| **National Stop Register (NSR), NeTEx** | All stop *places* with stop-place types (`onstreetBus`, `railStation`, `ferryStop`, …), national. | "Current stop places" NeTEx export (single zip). | More structured (mode per stop) but NeTEx XML is heavier to parse than a CSV. Fallback if GTFS stop quality is poor. |
| **Entur Journey Planner GraphQL** (`nearest`, `stopPlace`) | Per-query lookups, incl. departures. | Online API, per-query. | ❌ Not for a bulk offline join (thousands of lakes = thousands of calls). Keep the join offline like roads/elevation. |

**Verify before trusting:**
- Confirm the GTFS download URL is stable and open (Entur data is published under **NLOD**;
  attribution to **Entur / Kollektivdata** required — see Credits below).
- `stops.txt` mixes real boarding stops with parent stations / quays (`location_type` 1 =
  station, 0 = stop/platform, plus `parent_station`). Decide which rows count as a
  "reachable stop" — simplest defensible v1: keep `location_type == 0` (actual stop points).
- A stop existing ≠ a stop with service. Optional quality filter: keep only stops
  referenced in `stop_times.txt` (i.e. actually served). Note this as a v2 refinement;
  for v1 raw `stops.txt` points are acceptable.

**Hand-validate before wiring through** (pick known cases):
- A lake near a served bus stop / station should get a small `transit_distance_m`
  (e.g. a lake just outside a town in the default Oslo/Akershus bbox).
- A remote mountain lake should get a large distance (far from any stop).

## How transit affects the score (a mode toggle that swaps the inputs)

The accessibility card gets a **toggle: arrive by *nearest road* or by *nearest public-
transport stop***. It is **mutually exclusive** — one mode at a time, not a best-of/`max`.
The selected mode **swaps the data that feeds the whole accessibility dimension**:

- **Distance** scored is the chosen mode's distance — `road_distance_m` (*Bil*) or
  `transit_distance_m` (*Kollektiv*).
- **Climb** scored is the climb of that **same origin** — road→lake (*Bil*) or
  **stop→lake** (*Kollektiv*). The climb slider must reflect the chosen mode, so the
  climb-to-the-nearest-stop must be computed too (see Python side), not reused from the
  road.

So the composition shape from task 39 is unchanged — still
`Math.min(distScore, climbScore)` — but **both inputs come from whichever origin the
toggle selects**:

```
origin       = toggle == "transit" ? nearest stop : nearest road
distScore    = scoreAccess(origin.distance_m, arMin, arMax)
climbScore   = scoreClimb(|origin.elevation_gain_m|, climbMax)
accessibility_score = Math.min(distScore, climbScore)
```

There is **no `max` / best-of** and no "both" option — the user explicitly wants a single
chosen access mode driving both the distance and the climb sub-scores. Default the toggle
to *Bil* (road) so existing behaviour is preserved when transit data is absent.

## Suggested design

### Python side
1. **New module** `src/telttur/transport.py` (sibling of `roads.py`):
   - `ensure_gtfs(cache_dir, ...)` — download the aggregated GTFS zip if absent, reuse the
     cache (mirror `ensure_dem` in `elevation.py` / `_ensure_nina_archive` in `fishing.py`;
     cache under `data_dir`). Per commit `9b02c1f`, discard the source zip after extracting
     `stops.txt` if it's large.
   - `load_stops(...) -> gpd.GeoDataFrame` — read `stops.txt`, build points from
     `stop_lat`/`stop_lon` in `CRS_WGS84`, apply the `location_type` filter, clip to the
     run bbox.
2. **Score it in `accessibility.py`.** Fold transit into `score_accessibility()` rather than
   a new dimension (the user framed this as *expanding* accessibility). Crucially, the
   transit path mirrors the road path **end to end, including elevation** — because the
   climb slider must score climb from whichever origin the toggle picks:
   - Add a `stops: gpd.GeoDataFrame | None` parameter. Reproject to `CRS_UTM33` and compute
     nearest-stop distance with `gpd.sjoin_nearest(..., distance_col=...)` — same pattern as
     the road distance, points instead of lines.
   - **Compute stop→lake elevation gain too.** Capture the nearest stop point per lake and
     sample the DEM exactly as the road path does (`nearest_points` + `sample_elevations`,
     `accessibility.py:69–88`). The stop *is* the nearest point (it's a point geometry), so
     this is simpler than the road case — no `nearest_points` needed, just sample the lake
     representative point and the stop.
   - Add two columns to `lakes.py`: `LakeCols.TRANSIT_DISTANCE_M = "transit_distance_m"` and
     `LakeCols.TRANSIT_ELEVATION_GAIN_M = "transit_elevation_gain_m"`. When no stops are
     present, set distance `inf` / gain `0.0` (mirror the empty-`drivable` guard at
     `accessibility.py:50`).
3. **Wire into the orchestrator** (`src/telttur/scoring/__init__.py:69`): load stops near the
   `ensure_dem` call and pass them into `score_accessibility(...)`.
4. **Config** (`config.py`):
   - `AccessibilityConfig` — add transit thresholds if road and transit warrant different
     cutoffs (a 1 km walk to a bus stop ≠ 1 km to a road). Reuse `AccessibilityThresholds`
     shape, or add `transit_thresholds`. Keep `config.yaml` lean — only add knobs that are
     actually needed (CLAUDE.md).
   - Interactive slider: add an `InteractiveTransitRange` (or reuse
     `InteractiveAccessibilityRange`) under `InteractiveControlsConfig` (~line 87) and surface
     it in `build_config_block()`'s `interactive_cfg` (`data_export.py:169`).
5. **Export** — add `LakeCols.TRANSIT_DISTANCE_M` and `LakeCols.TRANSIT_ELEVATION_GAIN_M`
   to `optional_cols` in `build_lake_data` (`data_export.py:36`); present columns flow
   through automatically.

### Frontend side (`web/app.js`, single file)
6. **Access-mode toggle.** Add a two-option toggle to the accessibility card — *Bil*
   (road) / *Kollektiv* (transit) — mutually exclusive, defaulting to *Bil*. Hide / disable
   the *Kollektiv* option when `transit_distance_m` is absent from the dataset. Read it in
   `readControlState` (~254) as `cs.accessMode`.
7. **Mode-aware inputs to the existing score.** No `scoreTransit`, no best-of, no second
   pair of sliders. Keep the **existing distance + climb sliders** and just swap the *field*
   they read based on `cs.accessMode`. In `computeScores` (~316), generalise the current
   road-only block:
   ```js
   const dist = cs.accessMode === "transit" ? fields.transit_distance_m : fields.road_distance_m;
   const gain = cs.accessMode === "transit" ? fields.transit_elevation_gain_m : fields.elevation_gain_m;
   if (cs.accessOn && dist != null) {
     const distScore  = scoreAccess(dist, cs.arMin, cs.arMax);
     const climbScore = gain != null ? scoreClimb(Math.abs(gain), cs.climbMax) : null;
     live.accessibility_score = climbScore != null ? Math.min(distScore, climbScore) : distScore;
     scores.push(live.accessibility_score);
   }
   ```
   The distance/climb sliders keep the same bounds; if road vs transit need different
   default ranges, surface both defaults from config and apply the matching one on toggle.
8. **Card wiring** (`buildControls`, ~659–689): add the toggle above the existing sliders;
   on change, re-score via `teltturUpdate` (same as the sliders) and refresh the slider
   labels to whatever the new mode implies. No new sliders are added.
9. **Popup** (`buildPopup`, ~409–421): show both distances when present — the existing
   "Avstand til vei" row plus a new "Avstand til kollektivstopp" row (and, alongside the
   existing climb row, the transit climb when in/relevant to transit mode).
10. **i18n** (Norwegian only — English removed in task 34): add keys e.g.
    `transit_distance` ("Avstand til kollektivstopp"), `access_mode_road` ("Bil"),
    `access_mode_transit` ("Kollektiv"), and a toggle label. Update the `accessibility_info`
    tooltip to explain the road/transit toggle.

## Notes / constraints
- **Keep `config.yaml` lean** — the GTFS URL + filename are constants in `transport.py`
  (like `AR5_WMS_URL` in `landcover.py`), not config. Add a config knob only if a real
  per-region need appears.
- **Offline, cached join** — download once, score offline, consistent with N50 / DTM / NINA
  caches. National runs: `stops.txt` is small (~60k rows), so the join is cheap.
- **Don't over-build** (CLAUDE.md DRY/KISS): v1 = horizontal distance to nearest stop plus
  the stop→lake climb (needed for the toggle). Defer service-frequency weighting (only
  count *served* stops, weight by departures/day) to a follow-up; note it but don't build.
- **Credits / licensing** (task 29, credits block in `app.js` ~998 / CLAUDE.md Data Sources
  table): add **Entur** (public-transport data, NLOD). Cite the dataset/portal used.

## Acceptance criteria
- [ ] An authoritative Entur stop dataset is chosen and documented, validated against a few
      hand-checked lakes (one near a served stop, one remote).
- [ ] Stop data is downloaded once and cached; re-runs reuse the cache.
- [ ] Each lake carries `transit_distance_m` and `transit_elevation_gain_m` (distance and
      climb to the nearest stop), both exported in `data.js`.
- [ ] The accessibility card has a **Bil / Kollektiv toggle** (mutually exclusive, default
      *Bil*); selecting a mode makes **both** the distance and climb sub-scores read that
      mode's fields, still combined via `Math.min(distScore, climbScore)`. No best-of/`max`.
- [ ] Toggling re-scores and re-colours markers; the *Kollektiv* option is hidden when no
      transit data is present.
- [ ] Popup shows distance to both the nearest road and the nearest public-transport stop.
- [ ] Entur is attributed in the credits and CLAUDE.md Data Sources table.
- [ ] `uv run ruff check`, `uv run ruff format`, `uv run ty check` all pass.
