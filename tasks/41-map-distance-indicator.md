# Task 41 – Distance indicator on the map

Round 10 item: *"add a distance indicator to the map."*

## Objective

Give the user a sense of scale on the map by adding a distance/scale indicator. With
no scale reference, distances between lakes, roads, and towns are hard to judge.

## Recommended approach

Use Leaflet's built-in **scale control** — zero dependencies, one line:

```js
L.control.scale({ metric: true, imperial: false, maxWidth: 120 }).addTo(map);
```

Add it in `initMap()` (`web/app.js`, ~446) right after the map is created /
tile layer is added. Metric only (Norway). This renders a small scale bar
(e.g. "200 m" / "1 km") in a map corner that updates as the user zooms.

## Placement

- Default Leaflet position is `bottomleft`. Check it doesn't collide with the
  attribution control (`bottomright` by default) or the controls/criteria pane
  (top-right per task 12 rebrand). `bottomleft` should be clear — verify in the
  running app and override `position` only if it overlaps.
- Style: confirm it reads well over the greyscale Kartverket base tiles. Add a minimal
  rule in `web/style.css` (e.g. semi-opaque white background, subtle border) only if
  the default look clashes with the existing UI.

## Optional (only if the user wants more than a scale bar)

A measure-distance tool (click-to-measure a polyline) is a heavier feature
(`leaflet-measure` plugin or a small custom handler). The round-10 note says
"distance indicator", which the scale bar satisfies. **Do not add a measure plugin
unless the user explicitly asks** — it conflicts with the lightweight-deps preference.

## Steps

1. Add `L.control.scale(...)` in `initMap()`.
2. Run the app, verify the scale bar appears, updates on zoom, and doesn't overlap
   other controls.
3. Add a small `style.css` tweak only if needed for legibility.

## Acceptance criteria

- [ ] A metric scale bar is visible on the map and updates with zoom level.
- [ ] It does not overlap the criteria pane, attribution, or zoom controls.
- [ ] No new third-party dependency added.
