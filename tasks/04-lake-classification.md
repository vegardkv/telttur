# Task 4: Lake Classification by Building Density

## Objective
Enable and test the lake classification feature that color-codes lakes by cabin/building density.

## Context
The code in `src/telttur/lake_classification.py` counts buildings within a buffer around each lake and classifies as low/medium/high. This needs to be tested with real data and thresholds tuned.

## Steps

1. **Enable lake classification** in `config.yaml`:
   ```yaml
   lake_classification:
     enabled: true
     building_buffer_m: 500
   ```

2. **Run the pipeline** and check if building data is extracted correctly:
   ```bash
   uv run telttur generate --skip-download
   ```

3. **Inspect the building data**:
   - Verify the building layer is found in the FGDB
   - Check what building types exist (residential, cabin/hytte, commercial, etc.)
   - Consider filtering to only count cabins/residential buildings (exclude barns, garages, etc.)

4. **Tune classification thresholds** in `classify_lakes_by_density()`:
   - The current thresholds (≤5 = low, ≤20 = medium, >20 = high) are arbitrary
   - Run on a test area and check the distribution
   - Adjust so that roughly: 40% low, 40% medium, 20% high (or similar useful split)

5. **Verify visualization**:
   - Lakes should show distinct colors (blue = few buildings = good for camping)
   - Lake popup should show building count and classification

## Acceptance Criteria
- [ ] Building data is correctly extracted from N50
- [ ] Lakes are color-coded by building density
- [ ] Classification thresholds produce a useful distribution
- [ ] Lake popups show building count and density class
