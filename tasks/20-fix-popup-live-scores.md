# Task 20 – Fix popup labels to reflect interactive changes

## Problem

When a user adjusts scoring sliders or toggles, the marker colours update but the popup content remains stale. The popup is built once in `buildPopup()` during `initMap()` and is never regenerated.

## Current behaviour

- `teltturUpdate()` recalculates scores and updates `marker.setStyle()`, but `marker.bindPopup()` is only called once at init time.
- Opening a popup after moving a slider shows the **original** pre-computed scores, not the interactively computed ones.

## Solution

Re-bind (or lazily rebuild) popup content whenever a popup is opened, using the **current** slider/checkbox state to recompute scores. Approaches:

1. **Lazy popup on `popupopen`**: Instead of pre-binding HTML, attach a `popupopen` listener that rebuilds content from the current slider values each time the popup is opened.
2. **Store re-computation function**: Store the scoring function reference on the marker and invoke it when the popup opens.

Option 1 is simpler and sufficient.

### Implementation notes

- Extend `buildPopup()` (or create a new function) to accept the current control state and recompute per-dimension scores (reuse `scoreAccess`, `scoreCabin`, `scoreAr5` already in `app.js`).
- On the marker's `popupopen` event, call `marker.getPopup().setContent(...)` with the freshly built HTML.
- Keep the initial `bindPopup` for the first render so popup dimensions are set.

## Files to modify

- [web/app.js](../web/app.js) — popup binding logic, `buildPopup()`, `initMap()`

## Acceptance criteria

- Adjusting any slider or toggle, then clicking a marker, shows updated score badges reflecting current settings.
- No performance regression (popup rebuild is lightweight).
