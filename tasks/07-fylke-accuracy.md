# Task 7: Fylke Bounding Box Accuracy & Multi-Fylke Support

## Objective
Improve the fylke overlap detection and ensure multi-fylke downloads merge correctly.

## Context
The current `FYLKE_BOUNDS` in `download.py` uses hardcoded approximate bounding boxes. These should be verified against real data. Also, when the user's bbox spans multiple fylker, the resulting data from each must be merged correctly.

## Steps

1. **Verify fylke bounding boxes**:
   - Compare `FYLKE_BOUNDS` values against actual fylke boundaries
   - Use the Geonorge API's area list as ground truth: `GET /api/codelists/area/ea192681-d039-42ec-b1bc-f3ce04c189ac`
   - Update any incorrect bounds

2. **Check for missing fylker**:
   - The current dict may be missing newer fylker after the 2024 redistricting
   - Ensure all current fylke codes are present

3. **Test multi-fylke download**:
   - Use a bbox that spans two fylker (e.g., Innlandet + Akershus border)
   - Verify both FGDBs are downloaded
   - Verify roads/lakes/landcover from both are merged without duplicates at the border

4. **Consider dynamic fylke lookup**:
   - Instead of hardcoded bounds, query the Geonorge API areas endpoint at runtime
   - Cache the result for future runs

## Acceptance Criteria
- [ ] All Norwegian fylker are represented in the lookup
- [ ] Bbox spanning two fylker downloads both correctly
- [ ] Data from adjacent fylker merges without visible gaps or duplicates
