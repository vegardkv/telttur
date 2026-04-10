# Task 8: Slope Analysis Around Lakes (Future Enhancement)

## Objective
Add terrain slope analysis around lake shores to estimate probability of finding flat camping spots.

## Context
Kartverket's DTM 10 Terrengmodell (UUID: `dddbb667-1303-4ac5-8640-7ec04c0e3918`) provides 10m resolution elevation data as GeoTIFF. Slope can be computed from this DEM.

## Dependencies
- Additional Python packages: `rasterio`, `scipy` (or `richdem`)
- DTM 10 data downloaded from Geonorge

## Steps

1. **Add `rasterio` dependency**:
   ```bash
   uv add rasterio
   ```

2. **Extend `download.py`** to also download DTM 10 tiles for the bbox area.

3. **Create `src/telttur/slope.py`**:
   - Load DTM GeoTIFF with rasterio
   - For each lake: extract elevation values within a buffer (e.g., 200m) around the shore
   - Compute slope from the DEM grid (using numpy gradient or rasterio's terrain tools)
   - Compute average slope in the buffer zone
   - Classify: <5° = flat (good), 5-15° = moderate, >15° = steep

4. **Integrate with lake classification**:
   - Add `slope_class` and `slope_color` columns to the lakes GeoDataFrame
   - Combine with building density for an overall "camping suitability" score

5. **Update map visualization**:
   - Show combined suitability score as lake color
   - Or use a bivariate color scheme: x-axis = density, y-axis = slope

## Acceptance Criteria
- [ ] DTM data downloads correctly
- [ ] Slope is computed correctly for lake surroundings
- [ ] Lakes are classified by slope
- [ ] Combined suitability score considers both density and slope
