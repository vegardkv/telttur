# Task 42: Fishing Score Improvements

## Objective
Improve the robustness and honesty of the fishing score by accounting for the
nature of the underlying NINA data — point observations, not population surveys.

## Background

The fishing dimension (`src/telttur/scoring/fishing.py`) scores a lake by which
prized fish genera are present within a buffer around the lake. Presence is
derived from the **NINA Vanndata fisk** dataset, which is published to GBIF as a
DarwinCore archive of **individual point observations** (occurrence records).

Two properties of this data are currently glossed over:

1. **Point observations, not abundance.** Each record is a single sighting/catch
   at a coordinate. The data says nothing about population size, density, or how
   reliably a species can be caught. One lucky observation and a thriving
   fishery look identical in the current score.
2. **Spatial join, not lake identity.** Observations are mapped to lakes purely
   by location (a spatial join against a buffered lake polygon, `score_fishing`).
   The `occurrence.txt` archive very likely carries a waterbody/lake name field
   (e.g. `waterBody`, `locality`) that is currently ignored — we only read
   `scientificName`, `decimalLatitude`, `decimalLongitude`. Coordinate precision
   is ~100 m and the buffer is configurable, so an observation can be attributed
   to a neighbouring lake, or shared across two lakes that fall inside the same
   buffer.

The current output columns are `fish_species_count` and `fish_genera_mask`
(a bitmask of present prized genera). Crucially, **observation counts are
discarded** — `_build_genera_mask` only records presence/absence.

## Suggested Improvements

These are independent; pick whichever give the best value-for-effort.

### 1. Carry observation counts, not just presence (low effort, high value)
Add a per-lake, per-genus observation count instead of a single presence bit.
- Capture the number of observations behind each set genus bit (e.g. an extra
  `fish_genera_counts` structure, or a parallel per-genus count array).
- This unlocks every downstream idea below.

### 2. Flag single-observation species (low effort)
When a species/genus is backed by only **one** observation in/near a lake, flag
it as low-confidence in the UI (e.g. a "(1 obs)" badge or a muted style on the
genus chip). Communicates "someone caught one once" vs. "well-documented".

### 3. Let observation count influence the score (medium effort)
Today the score is a binary fraction of desired genera present. Consider
weighting presence by evidence strength, e.g. a saturating confidence factor
`1 - exp(-n / k)` (or a simple banding: 1 obs = partial credit, ≥N obs = full
credit). A genus with 1 observation should not score the same as one with 30.
Keep it tunable via `FishingConfig`.

### 4. Use the waterbody/lake name field for attribution (medium effort)
Inspect `occurrence.txt` for a lake/waterbody name column. If present, prefer
matching observations to lakes by name (where N50 lake names are available),
falling back to the spatial join only when the name is missing or ambiguous.
This reduces mis-attribution from the coordinate-only join. Validate against a
few hand-checked lakes before trusting it.

### 5. Surface data caveats / confidence in the UI (low effort)
Beyond the info-tooltip text (already updated), consider showing per-lake
evidence in the popup — e.g. total observation count, or a small
"data confidence: low/medium/high" indicator derived from observation counts.

### 6. Consider observation recency (optional, higher effort)
The archive likely has an `eventDate`. Very old observations (decades) may not
reflect the current fishery (stocking changes, acidification, rotenone
treatment). A recency weighting could down-weight stale records. Lower priority —
validate that `eventDate` is well-populated first.

## Notes / Constraints
- Keep `FishingConfig` lean (CLAUDE.md design principles); only add knobs that
  earn their place.
- Scoring math currently lives JS-side (`scoreFishing` in `web/app.js`); the
  Python side exports raw fields. Decide deliberately where new logic belongs —
  raw counts in `data.js`, scoring weights applied in JS, to keep the frontend
  interactive.
- Start by actually inspecting `occurrence.txt` columns; several suggestions
  hinge on which fields NINA ships.

## Acceptance (suggested, scope to chosen items)
- Observation counts are available per lake/genus in `data.js`.
- Single-observation species are visually distinguishable in the UI.
- (If pursued) the fishing score reflects evidence strength, configurable via
  `FishingConfig`.
