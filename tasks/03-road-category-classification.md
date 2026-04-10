# Task 3: Improve Road Category Classification

## Objective
Ensure roads are correctly classified by category (Europavei, Riksvei, Fylkesvei, etc.) with different buffer colors.

## Context
N50 road data may use different attribute names/values than expected. The current code guesses `vegkategori` as the column name with single-letter codes (E/R/F/K/P/S). This needs to be verified and adjusted to match the actual data.

## Steps

1. **Inspect the actual road attribute values**:
   ```python
   import geopandas as gpd
   gdf = gpd.read_file("data/n50/<fylke>/<file>.gdb", layer="<road_layer>")
   print(gdf.columns.tolist())
   # For each potential category column:
   print(gdf["<column>"].value_counts())
   ```

2. **Update `ROAD_CATEGORIES` mapping** in `src/telttur/roads.py`:
   - Map actual attribute values to labels and colors
   - The current mapping uses first-letter lookup — adjust if the real values differ

3. **Update `buffer_roads()` groupby logic** to use the correct column and value mapping.

4. **Verify** that the HTML map shows different colors for different road types.

5. **(Optional) Future extension**: Different buffer distances per road type (e.g., larger buffer for E/R roads where parking is more likely).

## Acceptance Criteria
- [ ] Road buffer polygons have visually distinct colors per road category
- [ ] Legend correctly labels each road type
- [ ] All road types in the data are handled (no "unknown" categories unless truly unknown)
