# Task 23 – Dual-handle range slider for accessibility

## Goal

Replace the two separate min/max accessibility sliders with a single **dual-handle range slider** that lets the user define a preferred distance range in one interaction.

## Current state

Two independent `<input type="range">` elements for min and max accessibility distance. This works but is clunky — the user can accidentally set min > max, and it takes twice the vertical space.

## Options

Since vanilla HTML does not support dual-handle range inputs, consider a lightweight library:

1. **[noUiSlider](https://refreshless.com/nouislider/)** (~30 KB minified, no dependencies, MIT license) — well-established, works with vanilla JS, supports dual handles, tooltips, and pips. Recommended.
2. **Custom CSS with two overlapping `<input type="range">`** — possible with vanilla JS but hacky, cross-browser issues.
3. **[Rangeslider.js](https://rangeslider.js.org/)** — another lightweight option.

### Recommendation

Use **noUiSlider**. It's dependency-free, works perfectly with vanilla JS, and is widely used.

## Implementation

1. Add noUiSlider CSS and JS via CDN in `index.html`:
   ```html
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15/dist/nouislider.min.css">
   <script src="https://cdn.jsdelivr.net/npm/nouislider@15/dist/nouislider.min.js"></script>
   ```
2. In `buildControls()` (or the new card system from task 22), create a `<div>` container for the slider and initialise it with `noUiSlider.create()`.
3. Configure: range `[0, slider_max_m]`, two handles at `[min_m, max_m]`, step 100, connect between handles.
4. On `update` event, read both handle values and call `teltturUpdate()`.
5. Remove the old two-slider markup for accessibility.

### Note on task ordering

If task 22 (cards) is implemented first, integrate the range slider directly into the accessibility card. Otherwise, integrate into the existing panel and refactor later.

## Files to modify

- [web/index.html](../web/index.html) — add noUiSlider CDN links
- [web/app.js](../web/app.js) — replace accessibility slider creation
- [web/style.css](../web/style.css) — optional styling overrides for noUiSlider

## Acceptance criteria

- A single dual-handle slider controls the accessibility min/max range.
- Current values are displayed (e.g. "200 m – 2000 m").
- Handles cannot cross each other (min ≤ max enforced by the library).
- Scoring updates live as handles are dragged.
- noUiSlider loaded from CDN, no build step required.
