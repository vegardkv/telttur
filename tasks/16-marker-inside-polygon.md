# Task 16: Marker Placement Inside Polygon

## Objective
Place lake markers at a guaranteed interior point instead of the centroid. Many lakes have irregular shapes (crescents, L-shapes) where the centroid falls outside the polygon, making the marker float over land.

## Context
Shapely provides `representative_point()` which returns a point guaranteed to lie within the geometry. This is a drop-in replacement for `centroid` in the marker placement code.

## Steps

1. **Update `_add_lake_markers()` in `src/telttur/map_generator.py`**:
   - Replace `geom.centroid` with `geom.representative_point()`
   - This affects the `location` passed to `folium.CircleMarker`

2. **Update `_build_lake_data_block()` in `src/telttur/maputils/interactivity.py`**:
   - The lake data lookup key is based on `centroid.y, centroid.x` — update to use `representative_point()` so the key matches the marker position

3. **Verify** on a regional map (e.g. `config_akershus.yaml`) that markers now sit visually inside their lake polygons.

## Acceptance Criteria
- [ ] All markers are placed at a point inside the lake polygon
- [ ] Interactive controls still correctly identify markers (lookup key matches)
- [ ] No visual regression on the map
