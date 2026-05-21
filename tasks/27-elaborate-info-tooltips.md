# Task 27 – Elaborate scoring info tooltips

## Goal

Expand the info (ⓘ) tooltips on each scoring dimension card to include a brief explanation of **how** the score is calculated, not just what the dimension means.

## Background

The current tooltips (added in task 22) describe each dimension in one sentence. Users have no visibility into the scoring mechanics — e.g. what thresholds drive each level, or how the data is sourced.

For AR5 land use data specifically: the pipeline can download AR5 data via multiple WMS/WFS approaches, but in practice only one download method works reliably (the others often return HTTP 400). The info text should note the data source without exposing internal implementation details.

## Scope

### Per-dimension info text updates

Expand each tooltip to ~2–3 sentences covering:

1. **What it measures** (keep existing text)
2. **How scoring works** — brief note on the scoring curve (e.g. "Lakes within your preferred range score Excellent; scores degrade gradually beyond that range")
3. **Data source** where relevant (e.g. "Based on N50 building data" or "Based on AR5 land use classification from Kartverket")

### Suggested info texts

- **Cabin density**: Current text + "Score is based on building density within a buffer zone around the lake. Below your threshold = Excellent; degrades as density increases beyond it. Data: N50 building layer."
- **Hiking distance**: Current text + "Lakes within your preferred range score Excellent; scores degrade symmetrically beyond the range. Data: distance to nearest N50 road."
- **Urbanization (AR5)**: Current text + "Score is based on distance to residential and industrial zones. Beyond 2× the buffer distance = Excellent. Data: AR5 land use classification (Kartverket)."
- **Fishing**: Current text + "Score is based on the fraction of your selected fish genera that are present. Data: fish species records."

### Tooltip styling

The tooltips may need to be slightly wider (currently 180px) to accommodate the longer text. Consider 220–240px.

## Files to modify

- [web/app.js](../web/app.js) — update `I18N` entries for `*_info` keys (both `en` and `no`)
- [web/style.css](../web/style.css) — adjust `.tt-info-tip` width if needed

## Acceptance criteria

- Each scoring dimension tooltip explains how the score is calculated in plain language
- Data sources are mentioned where appropriate
- Both English and Norwegian translations are updated
- Tooltip remains readable (not excessively long)
