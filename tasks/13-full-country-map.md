# Task 13: Full Country Map for Static Hosting

## Objective
Create a map covering all of Norway that can be served as a static HTML file on GitHub Pages (or similar). The file must be small enough to load and interact with in a browser.

## Context
The current pipeline processes one or a few fylker at a time and produces HTML files that can grow large (50+ MB for a single fylke). A national map requires aggressive optimization to keep the file size manageable.

## MVP Scope
- Grayscale base tile layer (no vector data baked in)
- Lakes shown as point markers (not polygons) — clickable with reduced metadata
- No road buffers, no landcover polygons in the MVP

## Steps

1. **Pre-process lake data for all fylker**:
   - Run the pipeline for each fylke to extract lake centroids, areas, and basic metadata
   - Store as a lightweight format (CSV or GeoJSON with point geometries only)
   - Strip unnecessary metadata — keep only: name, area, tentability score, coordinates

2. **Evaluate file-size reduction strategies**:
   - **Marker clustering**: Use `folium.plugins.MarkerCluster` or Leaflet.markercluster to group nearby lakes at low zoom levels
   - **GeoJSON simplification**: Reduce coordinate precision (5 decimal places ≈ 1m accuracy)
   - **Data compression**: Embed data as compressed base64 and decompress in JS
   - **Lazy loading**: Split data by region and load on demand via `fetch()` from separate JSON files hosted alongside the HTML
   - **Vector tiles**: Pre-generate `.pbf` tiles with tippecanoe and serve with Leaflet.VectorGrid — best performance but more complex hosting

3. **Implement the MVP**:
   - Generate a single HTML with a grayscale tile layer (e.g., CartoDB Positron)
   - Add lake centroids as clustered markers
   - Popups with lake name, area, and tentability score
   - Target file size: <5 MB for the HTML itself (excluding external tile requests)

4. **Test in browser**:
   - Load time on a typical connection
   - Pan/zoom responsiveness with 10,000+ markers
   - Mobile performance

5. **Set up GitHub Pages deployment** (optional):
   - Add a GitHub Actions workflow to generate and deploy the map
   - Or document the manual deployment process

6. **(Future) Add interactive controls** — integrate with Task 11 if completed.

## Size Budget
| Component | Target |
|-----------|--------|
| HTML + JS boilerplate | <200 KB |
| Lake data (JSON) | <3 MB |
| Total HTML file | <5 MB |
| External tiles | loaded on demand |

## Alternative Approaches (if MVP is too large)
- **Multi-file static site**: `index.html` + per-fylke JSON files, loaded on demand
- **PMTiles**: Single-file tile archive hosted on static storage, read with HTTP range requests
- **SQLite + sql.js**: Embed a SQLite DB in the page, query in-browser

## Acceptance Criteria
- [ ] Map covers all of Norway with lake markers
- [ ] Markers are clickable with basic metadata (name, area, score)
- [ ] HTML file is ≤5 MB (or uses lazy-loaded data files)
- [ ] Map is responsive in the browser with 10,000+ markers
- [ ] Can be served from a static hosting platform (GitHub Pages)
