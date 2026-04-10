# Task 6: Performance Optimization for Large Areas

## Objective
Ensure the pipeline handles larger bounding boxes (e.g., whole fylke or multiple fylker) without excessive memory use or impractically large HTML files.

## Steps

1. **Test with a larger area** — e.g., whole Innlandet:
   ```yaml
   bbox:
     north: 62.8
     south: 60.1
     east: 12.6
     west: 7.5
   ```

2. **Measure**:
   - Processing time for each step
   - Output HTML file size
   - Memory peak (if possible)

3. **Optimize if needed**:
   - Increase `simplify_tolerance_m` (e.g., 100 or 200) for large areas
   - Consider chunked reading of FGDB files (`geopandas.read_file(..., bbox=...)`)
   - Consider using `where` SQL filter in `fiona.open()` to pre-filter
   - For very large areas: write GeoJSON to separate files and use Leaflet's lazy-loading

4. **Add adaptive simplification**:
   - Auto-compute simplification tolerance based on bbox area
   - Or warn the user if estimated output will be >50MB

5. **Test HTML rendering performance**:
   - Open large maps in the browser
   - Check if panning/zooming is still responsive
   - If too slow, consider switching to vector tiles (Leaflet.VectorGrid) — future work

## Acceptance Criteria
- [ ] Pipeline completes for a full fylke within reasonable time
- [ ] Output HTML file is <50MB
- [ ] Map is usably responsive in the browser
- [ ] Simplification produces visually acceptable results
