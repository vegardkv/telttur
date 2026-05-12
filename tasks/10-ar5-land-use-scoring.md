# Task 10: AR5 Land Use Scoring

## Objective
Add a new scoring dimension based on AR5 land use data: proximity to industrial/commercial zones and significant residential areas should reduce the tentability score.

## Context
The existing scoring system has two dimensions — cabin density (N50 buildings) and accessibility (road distance). AR5 is a different data source (NIBIO) that classifies land use into types like `bebygd` (built-up), `samferdsel` (transport), `dyrka mark` (farmland), etc. The AR5 WMS layer is already integrated in `landcover.py` for visualization, but its data is not yet used for scoring.

Cabin density partially captures residential proximity, but AR5 provides a more comprehensive view of built-up and industrial areas that aren't necessarily covered by individual building counts.

## Steps

1. **Research AR5 land use categories**:
   - Identify which AR5 `Arealtype` values correspond to industrial/commercial zones
   - Identify which values represent significant residential areas
   - Check if AR5 WFS (vector) is available from NIBIO, or if the WMS needs to be queried differently for analysis

2. **Download or query AR5 vector data**:
   - Option A: Use WFS endpoint from NIBIO to fetch AR5 polygons within the bbox
   - Option B: Use the existing N50 `arealdekke` layers which contain similar categories
   - Prefer WFS if available, as AR5 is the authoritative source

3. **Create scoring logic** in `scoring.py`:
   - For each lake, compute the distance to the nearest industrial/commercial polygon
   - For each lake, compute the distance to the nearest significant residential polygon
   - Apply configurable distance thresholds, e.g.:
     ```yaml
     scoring:
       ar5_land_use:
         enabled: true
         industrial_buffer_m: 2000    # lakes within this distance get penalized
         residential_buffer_m: 1000
     ```
   - Lakes far from both get EXCELLENT; lakes near either get POOR/TERRIBLE

4. **Integrate into `compute_tentability()`**:
   - Add the new dimension to the composite score (worst-case across all dimensions)

5. **Update map popups** to show the AR5-based score component.

## Acceptance Criteria
- [ ] AR5 land use polygons are fetched for the bbox area
- [ ] Lakes near industrial/commercial zones receive a reduced score
- [ ] Lakes near significant residential areas receive a reduced score
- [ ] Distance thresholds are configurable
- [ ] New scoring dimension integrates with the existing composite tentability score
