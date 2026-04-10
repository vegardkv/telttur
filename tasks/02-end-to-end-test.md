# Task 2: End-to-End Pipeline Test & Bug Fixes

## Objective
Run the full `telttur generate` pipeline for a small test area and fix any issues that arise.

## Context
The pipeline is: download → extract roads → buffer → extract lakes → classify reachability → generate HTML map. Each module has been written but not tested with real data.

## Steps

1. **Run the full pipeline**:
   ```bash
   uv run telttur generate --config config.yaml
   ```

2. **Fix any runtime errors** — common expected issues:
   - Layer names not matching (see Task 1)
   - CRS mismatches during clipping or buffering
   - Empty GeoDataFrames causing errors downstream
   - Column name mismatches in style functions or popups

3. **Verify the output HTML**:
   - Open `output/map.html` in a browser
   - Check that the Kartverket base map tiles load
   - Check that road buffer polygons are visible
   - Check that lake polygons are visible
   - Check that the layer control toggle works
   - Check that clicking a lake shows a popup

4. **Test with different parameters**:
   - Change `buffer_distance_m` to 500 and 5000, regenerate with `--skip-download`
   - Verify the buffer visually changes

5. **Fix the `--skip-download` flag** if it doesn't correctly find existing .gdb files.

## Acceptance Criteria
- [ ] `uv run telttur generate` completes without errors
- [ ] `output/map.html` opens in a browser and shows a working map
- [ ] Road buffers are visible as semi-transparent colored polygons
- [ ] Lakes are visible as blue polygons
- [ ] Layer toggle and legend work
- [ ] `uv run ruff check src/` passes
