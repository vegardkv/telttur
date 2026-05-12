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

4. **Create `score_fishing()` in `scoring.py`**:
   - Define scoring logic based on the available data
   - If using geographic proxies: combine altitude, lake size, and connectivity
   - If using registry data: presence of fish species / stocking = higher score
   - Normalize to the existing 5-point tentability scale

5. **Integrate with `compute_tentability()`**:
   - Add as a new dimension (configurable, default enabled)
   - Update lake popups with fishing score details

6. **Add config options**:
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
