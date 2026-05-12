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

## Steps

1. **Research available data sources** — systematically check the sources listed above for API/download availability and coverage.

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
