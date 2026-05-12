# Task 9: Disable OSM Tile Layer by Default

## Objective
Remove the OpenStreetMap tile layer from the map by default, making it opt-in via configuration.

## Context
The map currently always includes an OSM tile layer as a fallback base layer (in `map_generator.py`). The primary base layers are Kartverket topographic tiles and a blank layer. The OSM layer adds clutter to the layer control and is rarely needed.

## Steps

1. **Add a config option** in `config.yaml`:
   ```yaml
   map:
     include_osm_layer: false
   ```

2. **Update `map_generator.py`** to conditionally add the OSM layer:
   - Read the `map.include_osm_layer` config value (default `false`)
   - Only add the `folium.TileLayer(tiles="OpenStreetMap", ...)` block when the flag is `true`

3. **Update `config.py`** to parse the new option with a `false` default.

4. **Verify** that the map renders correctly without the OSM layer and that enabling the flag brings it back.

## Acceptance Criteria
- [ ] OSM tile layer is not shown by default
- [ ] Setting `map.include_osm_layer: true` in config re-enables it
- [ ] Map still has Kartverket layers and blank layer as base options
