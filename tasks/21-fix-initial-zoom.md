# Task 21 – Fix initial zoom for the national map

## Problem

When loading the full Norway map (`data_norway.js`), the initial view is zoomed in on the south-east corner. The user must manually zoom out and pan to find the actual map extent.

## Current behaviour

In `initMap()`:

```js
const centerLat = (bbox[0] + bbox[2]) / 2;
const centerLng = (bbox[1] + bbox[3]) / 2;
map = L.map("map", { preferCanvas: true }).setView([centerLat, centerLng], 10);
```

The hardcoded zoom level `10` is appropriate for a single fylke but far too close for the national bbox (`[57.7, 4.0, 71.5, 31.8]`).

## Solution

Use `map.fitBounds()` instead of a fixed zoom level. This lets Leaflet compute the correct zoom automatically from the bbox.

```js
const bounds = L.latLngBounds(
  [bbox[0], bbox[1]],  // south-west
  [bbox[2], bbox[3]]   // north-east
);
map = L.map("map", { preferCanvas: true });
map.fitBounds(bounds);
```

Optionally add small padding: `map.fitBounds(bounds, { padding: [20, 20] })`.

## Files to modify

- [web/app.js](../web/app.js) — `initMap()` function

## Acceptance criteria

- Opening the national map shows all of Norway in view.
- Smaller regional maps (e.g. Akershus test) also display correctly.
