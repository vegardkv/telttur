# Task 12: Fishing Suitability Score

## Objective
Add a "fishing" scoring dimension to rate lakes (and potentially rivers) by their suitability for recreational fishing.

## Context
Fishing quality is inherently hard to quantify from geographic data alone. This task is intentionally open-ended and may require creative data sourcing. The goal is to find the best available proxy signals for fishing quality and combine them into a score.

## Research: Potential Data Sources

1. **Geonorge / Miljødirektoratet**:
   - Lakseregisteret (salmon registry) — known salmon rivers
   - Vannmiljø / Vann-Nett — water quality and ecological status data
   - Fiskeridirektoratet datasets — fish species presence, stocking records

2. **NINA (Norwegian Institute for Nature Research)**:
   - Fish population surveys
   - Biodiversity databases

3. **Inatur.no / Statsskog**:
   - Fishing license areas — existence of managed fishing implies good fishing
   - Public fishing areas (statsallmenning)

4. **Web scraping** (use cautiously, respect robots.txt):
   - Fishing forums (e.g., skandinaviskfiskeforum.no, fiskersiden.no)
   - Trip reports mentioning specific lakes
   - Sentiment / catch-rate extraction

5. **Geographic proxies**:
   - Lake size, depth (from bathymetric data if available)
   - Altitude (trout thrive at certain elevations)
   - River connectivity — lakes connected to rivers may have better fish populations
   - Water quality indicators (clarity, temperature from satellite data)

## Research Findings (Step 1)

### Source 1: NINA Vanndata fisk ⭐ RECOMMENDED

- **What**: DarwinCore Archive of fish species observations from NINA's water database
- **Provider**: Norsk institutt for naturforskning (NINA)
- **Geonorge UUID**: `997a8352-b825-424a-9999-125618d2a93e`
- **Download URL**: `https://ipt.nina.no/archive.do?r=vanninfofisk`
- **Format**: ZIP containing `occurrence.txt` (TSV, ~25 MB uncompressed, ~2.4 MB zipped)
- **Records**: ~84,980 georeferenced fish observations
- **Coverage**: National (Norway-wide), all records have lat/lon coordinates (WGS84)
- **Key columns**: `scientificName`, `decimalLatitude`, `decimalLongitude`, `locality`, `municipality`
- **Top species by count**: Salmo trutta (45,760), Perca fluviatilis (10,849), Salvelinus alpinus (9,001)
- **Unique locations**: ~31,187 distinct coordinate pairs
- **Coordinate precision**: ~100 m
- **Freshness**: Last updated April 2026
- **Integration effort**: Low — single HTTP download, standard TSV parsing, spatial join to lake polygons
- **Scoring approach**: Count fish species observed near/within each lake → more species = higher fishing score. Presence of prized species (trout, char, pike, perch) gives bonus.

### Source 2: Artskart / Artsdatabanken (Public API)

- **What**: Public API serving all species observations in Norway (from multiple data providers)
- **API base**: `https://artskart.artsdatabanken.no/publicapi/api/`
- **Endpoints**:
  - `/taxon?term=<name>` — search for species (returns TaxonId)
  - `/observations/list?taxonIds[]=<id>&pageSize=<n>` — fetch observations
- **Records for Salmo trutta**: ~60,949,333 (extremely large — includes electrofishing individual counts)
- **Pros**: Vast dataset, real-time API, covers all fish species
- **Cons**: Overwhelmingly large — 60M+ records for one species alone. No bulk spatial query. Pagination-heavy. Would need many API calls to cover Norway. Rate limits unknown.
- **Verdict**: **Not practical for batch/static map generation.** Could be useful for spot checks or validation but not as a primary data source.

### Source 3: Lakseregisteret (Anadromous Fish Registry)

- **What**: MapServer for anadromous fish populations (salmon, sea trout, sea char)
- **Provider**: Miljødirektoratet
- **API**: `https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer`
- **Layers** (10 total):
  - 0: `anadrome_vandringshinder_laks` (migration barriers)
  - 5: `anadrome_bestander_laks` (salmon populations)
  - 6–7: Sea trout / sea char populations
  - 8–9: Management regions
- **Format**: ArcGIS MapServer (queryable via REST)
- **Pros**: Authoritative government data on salmon/sea trout presence
- **Cons**: Only covers anadromous species (rivers/estuaries, not inland lakes). Focused on rivers. Not directly useful for lake-based fishing scoring.
- **Verdict**: **Limited relevance** — only applicable to rivers and coastal lakes with anadromous fish runs. Could supplement the NINA data for river-connected lakes.

### Source 4: Artsutbredelse Fisk (Havforskningsinstituttet)

- **What**: Fish species distribution dataset
- **Provider**: Havforskningsinstituttet (Institute of Marine Research)
- **Geonorge UUID**: `0fdd8501-cacd-40a4-9085-ac6d9a757a8d`
- **Download**: `https://kart.hi.no/datasett` (GML, GeoJSON, Shape)
- **Verdict**: **Marine focused** — covers sea fish distributions, not freshwater. Not relevant for lake fishing.

### Source 5: NVE Innsjødatabasen (Lake Database)

- **What**: NVE's official lake database with physical properties
- **Status**: ArcGIS services at `gis3.nve.no` were searched but no dedicated lake database service was found at the expected URLs. The service may have been retired or relocated.
- **Potential data**: Lake area, depth, altitude, outflow connectivity
- **Verdict**: **Not readily accessible via API.** The lake physical properties (area, altitude) are partially available from our existing N50 data. Depth data would be valuable but couldn't be located.

### Source 6: Inatur.no

- **What**: Norway's largest marketplace for hunting and fishing licenses
- **Content**: 5,669 listings including fishing areas with species info and pricing
- **API**: No public API found. Content is rendered client-side.
- **Verdict**: **No API available.** Web scraping would be fragile and legally questionable. Not viable.

### Source 7: Vannmiljø / Vann-Nett

- **What**: Water quality and ecological status data
- **Status**: API endpoints (`vannmiljodata.miljodirektoratet.no`) were unreachable from this environment.
- **Verdict**: **Could not verify accessibility.** May require VPN or specific network access.

### Geographic Proxies (from existing data)

- **Lake area**: Already computed as `area_m2` in the lakes GeoDataFrame
- **Altitude**: Not currently in the lake data; could be added via DEM overlay but adds complexity
- **River connectivity**: Not directly available; would require network analysis of waterways from N50

### Recommendation

**Primary source: NINA Vanndata fisk** — Best balance of coverage (national, 85K records, all georeferenced), data quality (authoritative, freshly updated), and integration ease (single ZIP download, standard format, spatial join to existing lake polygons).

**Scoring strategy**:
1. Download the NINA archive at pipeline time (or cache locally)
2. Parse the TSV into a GeoDataFrame of fish observation points
3. Spatial join to lake polygons (with small buffer for nearby observations)
4. Score each lake based on: number of species observed + presence of prized game fish
5. Lakes with no observations get a neutral/unknown score (not penalized)

**Supplementary**: Lake area (already available) could serve as a simple tiebreaker — larger lakes generally support more fish.

## Steps

1. ~~**Research available data sources**~~ ✅ — see findings above.

2. **Select the most promising 1–2 data sources** based on:
   - Coverage (national or regional)
   - Data quality and freshness
   - Ease of integration (API vs. manual download vs. scraping)

3. **Implement data fetching** — download or query the selected data source(s).

4. **Create `src/telttur/scoring/fishing.py`** following the dimension module convention:
   - Define scoring logic based on the available data
   - If using geographic proxies: combine altitude, lake size, and connectivity
   - If using registry data: presence of fish species / stocking = higher score
   - Normalize to the existing 5-point tentability scale
   - Export `SCORE_COLUMN = "fishing_score"` and `POPUP_FIELDS` listing the columns this dimension adds

5. **Add `FishingConfig` to `src/telttur/config.py`**:
   ```python
   class FishingConfig(BaseModel):
       enabled: bool = True
       # Source-specific fields TBD after research
   ```
   Add `fishing: FishingConfig = Field(default_factory=FishingConfig)` to `ScoringConfig`.

6. **Register the dimension in `src/telttur/scoring/__init__.py`**:
   - Import the new module: `from telttur.scoring import fishing`
   - Add `fishing` to `_DIMENSION_MODULES` (for popup auto-collection)
   - Add an `if config.fishing.enabled:` block in `process_scoring()`

7. **Add config options** (YAML):
   ```yaml
   scoring:
     fishing:
       enabled: true
       # Source-specific options TBD after research
   ```

## Acceptance Criteria
- [ ] At least one data source for fishing quality is identified and integrated
- [ ] Lakes receive a fishing suitability score
- [ ] Score is integrated into the composite tentability rating
- [ ] Lake popups show fishing score and contributing factors
- [ ] Data source and methodology are documented
