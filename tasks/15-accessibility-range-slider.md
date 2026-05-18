# Task 15: Accessibility Range Slider

## Objective
Replace the one-sided accessibility threshold sliders with a two-sided range slider (min and max distance). The "ideal" range represents Excellent; distances beyond or below the range degrade gracefully to Terrible.

## Context
Currently, accessibility scoring uses a monotonic scale: closer to road = better. In practice, users may want lakes that are *neither too close* (noisy roads) *nor too far* (hard to reach). A range slider captures this preference.

## Scoring Logic

Given a user-selected range `[min_km, max_km]`:

- **Within range** (`min_km ≤ d ≤ max_km`): Excellent (5)
- **Above range**:
  - `d ≤ max_km × 1.25`: Good (4)
  - `d ≤ max_km × 1.5`: Fair (3)
  - `d ≤ max_km × 2.0`: Poor (2)
  - `d > max_km × 2.0`: Terrible (1)
- **Below range**:
  - `d ≥ min_km × 0.75`: Good (4)
  - `d ≥ min_km × 0.5`: Fair (3)
  - `d ≥ min_km × 0.25`: Poor (2)
  - `d < min_km × 0.25`: Terrible (1)

If `min_km` is 0, the "below range" logic is disabled (any distance below max is fine).

## Steps

1. **Add range config to `InteractiveControlsConfig`**:
   - Replace `accessibility_thresholds` with a simpler model:
     ```python
     class InteractiveAccessibilityRange(BaseModel):
         enabled: bool = True
         min_m: float = 200.0   # default preferred minimum distance
         max_m: float = 2000.0  # default preferred maximum distance
         slider_max_m: float = 10000.0  # upper bound of the slider
     ```

2. **Update the interactive panel HTML** in `src/telttur/maputils/interactivity.py`:
   - Render two sliders: "Min distance" and "Max distance" (or a dual-handle noUiSlider if simple enough to embed)
   - If a dual-handle slider is too complex for inline JS, two separate sliders (min/max) are acceptable
   - Display current values in metres next to each slider

3. **Update the JS scoring function**:
   - Replace the monotonic `scoreAccess(dist)` with the range-based logic above
   - Read min/max values from the slider elements on each `teltturUpdate()` call

4. **Keep backward compatibility**:
   - The static (non-interactive) accessibility scoring in `src/telttur/scoring/accessibility.py` remains unchanged — it uses the existing threshold model for baked-in scores
   - The range slider only affects the *interactive* re-scoring in the browser

5. **Test** with `config_norway.yaml` that the sliders appear and markers update colours when adjusted.

## Acceptance Criteria
- [ ] Two sliders (or a dual-handle range) for accessibility min/max distance
- [ ] Scores degrade symmetrically above and below the range
- [ ] Marker colours update in real time when sliders are adjusted
- [ ] Default range (200 m – 2000 m) produces sensible colouring
