# Task 1: Validate Data Download & Inspect N50 FGDB Structure

## Objective
Run the download script for a small test area and document the exact layer names, schemas, and attribute values inside the N50 FGDB files.

## Context
The N50 Kartdata is downloaded as FileGDB (.gdb) format from Geonorge. The exact layer names and attribute schemas are not documented in advance — they must be discovered by inspecting the actual downloaded files.

## Steps

1. **Run the download command** for the default config (Innlandet region around Mjøsa):
   ```bash
   uv run telttur download --config config.yaml
   ```

2. **Inspect the .gdb file** to list all layers and their schemas:
   ```bash
   uv run telttur inspect <path-to-gdb>
   ```

3. **Document the findings** — update this file with:
   - Full list of layers in the FGDB
   - For the road layer(s): attribute names, especially the road category field (expected: `vegkategori` or similar)
   - For the water/lake layer(s): attribute names, especially the object type field (expected: `objtype`)
   - For the land cover layer(s): attribute names
   - For the building layer(s): attribute names

4. **Fix layer-matching logic** if the keywords in `find_road_layers()`, `find_lake_layers()` etc. don't match the actual layer names. Update the keyword lists in:
   - `src/telttur/roads.py` → `find_road_layers()`
   - `src/telttur/lakes.py` → `find_lake_layers()`
   - `src/telttur/landcover.py` → `find_landcover_layers()`
   - `src/telttur/lake_classification.py` → `find_building_layers()`

5. **Fix attribute-matching logic** if the road category field is not `vegkategori`, or the object type field is not `objtype`.

## Acceptance Criteria
- [ ] Download completes successfully for at least one fylke
- [ ] All layers in the FGDB are documented
- [ ] Layer-matching functions correctly find the right layers
- [ ] Attribute names used in the code match the actual data
- [ ] `uv run ruff check src/` passes
