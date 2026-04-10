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

## Findings (Innlandet / N50 FGDB)

Downloaded: `Basisdata_34_Innlandet_25833_N50Kartdata_FGDB.gdb`

### Full layer list

| Layer | Features | Key attributes |
|---|---|---|
| `N50_AdministrativeOmråder_grense` | 162 | objtype, datafangstdato, oppdateringsdato, malemetode, noyaktighet |
| `N50_AdministrativeOmråder_omrade` | 46 | objtype, kommunenavn, kommunenummer, fylkesnummer, fylkesnavn |
| `N50_AdministrativeOmråder_posisjon` | 127 | objtype, grensepunktnummer, grensepunkttype |
| `N50_Arealdekke_grense` | 612 753 | objtype, datafangstdato, oppdateringsdato |
| **`N50_Arealdekke_omrade`** | 316 624 | **objtype**, oppdateringsdato, navn, vatnlopenummer |
| `N50_Arealdekke_posisjon` | 15 488 | objtype, retningsverdi |
| `N50_Arealdekke_senterlinje` | 142 996 | objtype, vannbredde |
| `N50_BygningerOgAnlegg_grense` | 4 018 | objtype, datafangstdato |
| `N50_BygningerOgAnlegg_omrade` | 3 865 | objtype, bygningstype, betjeningsgrad, hytteeier, tilgjengelighet |
| **`N50_BygningerOgAnlegg_posisjon`** | 207 821 | **objtype**, bygningstype, betjeningsgrad, hytteeier, tilgjengelighet |
| `N50_BygningerOgAnlegg_senterlinje` | 10 875 | objtype, fler_linjer |
| `N50_Høyde_posisjon` | 21 367 | objtype, hoyde, medium |
| `N50_Høyde_senterlinje` | 138 660 | objtype, hoyde, medium |
| `N50_Restriksjonsområder_grense` | 5 274 | objtype, datafangstdato |
| `N50_Restriksjonsområder_omrade` | 1 039 | objtype, navn, vernedato, verneform, allmenningtype |
| `N50_Samferdsel_posisjon` | 2 275 | objtype, navn |
| **`N50_Samferdsel_senterlinje`** | 232 072 | **objtype**, **vegkategori**, typeveg, vegnummer, motorvegtype, medium, sporantall, banestatus |
| `N50_Stedsnavn_tekstplassering` | 78 008 | FeatureID, TextString, FontName |

### Road layer (`N50_Samferdsel_senterlinje`)
- Road category field: **`vegkategori`** (values: `E`, `F`, `K`, `P`, `R` — no `S` Skogsvei in this dataset)
- `objtype` values: `Veglenke` (roads), `Bane` (railway) — railways have `vegkategori=None`

### Water/lake layer (`N50_Arealdekke_omrade`)
- Object type field: **`objtype`**
- Lake-relevant `objtype` values: `Innsjø`, `InnsjøRegulert`
- River: `Elv`; other types: `Skog`, `Myr`, `DyrketMark`, `Tettbebyggelse`, `ÅpentOmråde`, `SnøIsbre`, etc.

### Land cover layer (`N50_Arealdekke_omrade`)
- Same layer as lakes; filtered by `objtype`
- All `objtype` values: `Alpinbakke`, `BymessigBebyggelse`, `DyrketMark`, `Elv`, `FerskvannTørrfall`, `Golfbane`, `Gravplass`, `Industriområde`, `Innsjø`, `InnsjøRegulert`, `Lufthavn`, `Myr`, `Park`, `Rullebane`, `Skog`, `SnøIsbre`, `SportIdrettPlass`, `Steinbrudd`, `Steintipp`, `Tettbebyggelse`, `ÅpentOmråde`

### Building layer (`N50_BygningerOgAnlegg_posisjon`)
- Object type field: **`objtype`** (value: `Bygning`)
- `bygningstype` (integer code) distinguishes building types (e.g. hytte/cabin vs house)

### Fixes applied
- `find_road_layers()`: narrowed to require `senterlinje` suffix — avoids reading `posisjon` (point) layer
- `find_lake_layers()`: narrowed to require `omrade` suffix — avoids reading grense/senterlinje layers
- `find_landcover_layers()`: narrowed to require `omrade` suffix — same reason
- `find_building_layers()`: narrowed to require `posisjon` suffix — avoids reading non-point building layers into density analysis
- Attribute names `vegkategori` and `objtype` are correct as-is in the code — no changes needed

## Acceptance Criteria
- [x] Download completes successfully for at least one fylke
- [x] All layers in the FGDB are documented
- [x] Layer-matching functions correctly find the right layers
- [x] Attribute names used in the code match the actual data
- [x] `uv run ruff check src/` passes
