# Task 18: First Viable Model — Map Polish

## Objective
Clean up the map output for the first publishable version: remove unnecessary layers and controls, lock in a single greyscale base map.

## Changes

1. **Remove AR5 WMS layer from map rendering**:
   - When `landcover_mode` is `"disabled"`, no land cover layer should be added (already the case)
   - Additionally, even when AR5 scoring is *enabled* for score computation, the AR5 overlay should **not** be rendered on the map as a visible layer
   - This is already controlled by `landcover_mode: disabled` in config — verify this is sufficient and that the AR5 scoring still works independently of the map layer

2. **Remove base map toggle**:
   - Currently the map adds multiple `TileLayer` options (Kartverket Topo, Kartverket Grey, OSM, None) with a `LayerControl`
   - For the first viable model, render only the greyscale layer (`topograatone`) with no layer switcher for base maps
   - Add a config option `map.base_map` with values: `"greyscale"` (default), `"topographic"`, `"selectable"` (current multi-layer behaviour)
   - When set to `"greyscale"` or `"topographic"`, only that single tile layer is added and the layer control shows only overlays (lakes, roads)

3. **Remove `LayerControl` clutter**:
   - With a single base layer and lakes as the only overlay (roads disabled for national), the layer control becomes unnecessary
   - If the only overlay is "Lakes", hide the layer control entirely

## Steps

1. Add `base_map: Literal["greyscale", "topographic", "selectable"]` to `MapConfig` with default `"greyscale"`
2. Update `generate_map()` to conditionally add tile layers based on `config.map.base_map`
3. Only add `LayerControl` when there are multiple overlays or `base_map == "selectable"`
4. Verify with `config_norway.yaml` that the map renders cleanly with just greyscale tiles + lake markers + interactive controls

## Acceptance Criteria
- [ ] Greyscale base map with no layer switcher when `base_map: greyscale`
- [ ] AR5 layer not visible on map regardless of AR5 scoring being enabled
- [ ] Interactive controls still function
- [ ] Existing configs (`config.yaml`, `config_akershus.yaml`) continue working with `base_map: selectable`
