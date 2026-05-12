# Task 14: Driving Distance Scoring

## Objective
Add a scoring dimension based on travel distance from a user-configured home location. Lakes closer to home receive a higher score.

## Context
Convenience matters — a pristine lake 6 hours away may be less appealing than a good lake 30 minutes from home. The user specifies their home coordinates and defines score thresholds based on travel time or distance.

## Steps

1. **Add home location to config**:
   ```yaml
   home:
     lat: 59.91
     lng: 10.75
     # Future: address lookup via Nominatim
   ```

2. **Add distance scoring thresholds**:
   ```yaml
   scoring:
     driving_distance:
       enabled: true
       thresholds:
         excellent_km: 30    # < 30 km straight-line
         good_km: 60
         fair_km: 100
         poor_km: 150        # > 150 km = terrible
   ```

3. **Implement MVP: straight-line distance**:
   - Create `score_driving_distance()` in `scoring.py`
   - Compute haversine distance from home to each lake centroid
   - Map distance to the 5-point tentability scale using the configured thresholds

4. **Integrate with `compute_tentability()`**:
   - Add as a new dimension in the composite score
   - Update lake popups with distance info (e.g., "32 km from home")

5. **Verify** on the map that lakes near the configured home location score higher.

6. **(Future) Real routing distance**:
   - Use OSRM (Open Source Routing Machine) or Valhalla for actual driving time
   - Self-hosted or public demo server (`router.project-osrm.org`)
   - Switch thresholds from km to minutes:
     ```yaml
     thresholds:
       excellent_min: 30
       good_min: 45
       fair_min: 75
       poor_min: 120
     ```
   - Rate-limit API calls and cache results
   - Consider pre-computing a drive-time isochrone and scoring by containment

7. **(Future) Address lookup**:
   - Allow `home.address: "Karl Johans gate 1, Oslo"` instead of lat/lng
   - Geocode via Nominatim (OpenStreetMap) at pipeline start

## Acceptance Criteria
- [ ] Home location is configurable via lat/lng in config
- [ ] Straight-line distance to each lake is computed
- [ ] Distance is mapped to a 5-point score using configurable thresholds
- [ ] Score integrates into the composite tentability rating
- [ ] Lake popups show distance from home
