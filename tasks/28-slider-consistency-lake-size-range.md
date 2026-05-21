# Task 28 – Slider consistency & lake size range slider

## Goal

1. Make the **accessibility range slider** (noUiSlider) visually consistent with the native `<input type="range">` sliders used elsewhere
2. Convert the **lake size filter** from a single min-value slider into a **range slider** (min + max), increase the upper bound, apply super-linear scaling, and make it clearer that this is a **filter** (not a scoring dimension)

## Problem

### Accessibility slider appearance

The accessibility dimension uses noUiSlider (a third-party range slider library), while cabin density and AR5 buffer sliders use native `<input type="range">`. The visual styles are noticeably different — different track heights, handle shapes, and colours. They should look consistent.

### Lake size filter

- Currently a single native slider controlling minimum lake area (0–100,000 m²)
- Upper bound of 100,000 m² (10 ha) is too low for national-scale maps — many interesting lakes are larger
- The scale is linear, which makes it hard to select small values when the range is large
- It's positioned among the scoring cards but is actually a **filter** — it hides lakes below the threshold rather than scoring them. This should be visually distinguished

## Design

### Accessibility slider styling

Option A: Style noUiSlider to match the native range inputs (custom CSS for `.noUi-*` classes).
Option B: Replace all native `<input type="range">` sliders with noUiSlider for consistent appearance.

Prefer **Option A** unless Option B is clearly simpler. The key requirement is visual consistency.

### Lake size range slider

- Convert to a two-handle range slider: **min** and **max** lake area
- Increase upper bound significantly (e.g. 10 km² = 10,000,000 m²)
- Apply **super-linear scaling** so the slider is usable across the full range. Options:
  - Logarithmic scale (map slider position → `10^x` area)
  - Quadratic/power scale
  - Piecewise linear with breakpoints
- Display values in human-readable units (m², ha, km²) using the existing `formatArea()` function
- Visually separate this from the scoring dimension cards (it's a filter, not a scoring dimension). E.g.:
  - Place it above or below the scoring cards with a label like "Lake size filter" / "Innsjøstørrelse (filter)"
  - Use a different card style or no card at all
  - Add a brief label: "Hide lakes outside this size range"

### I18N

Add translation keys for the new labels (both `en` and `no`).

## Files to modify

- [web/app.js](../web/app.js) — lake size range slider logic, filter update, I18N keys
- [web/style.css](../web/style.css) — noUiSlider custom styling, filter section styling
- [web/index.html](../web/index.html) — if noUiSlider needs to be loaded differently

## Acceptance criteria

- All sliders in the control panel look visually consistent
- Lake size uses a two-handle range slider with super-linear scaling
- Lake size filter clearly appears as a filter, distinct from scoring dimensions
- Values display in readable units (m², ha, km²)
- Upper bound accommodates large lakes (up to ~10 km²)
- Both languages updated
- No scoring regression
