# Task 11: Interactive Map Parameter Adjustment

## Objective
Allow users to adjust scoring priorities and parameters on-the-fly within the map, with live visual updates. Which parameters are exposed should itself be configurable, with sensible defaults.

## Context
Currently, all scoring parameters are set in `config.yaml` and baked into the HTML at generation time. To experiment with different weightings, the user must edit the config and regenerate the map. A more interactive approach would let users tweak parameters directly in the browser.

## Constraints
- Folium generates static HTML with embedded data — it has limited support for dynamic interactivity beyond layer toggling and popups.
- The solution should remain a static HTML file (no backend server required).

## Steps

1. **Evaluate Folium's capabilities**:
   - Test if Folium's `MacroElement` or custom JS injection can support sliders/controls
   - Check if marker styles can be dynamically updated via JavaScript

2. **If feasible with Folium**:
   - Inject a control panel (HTML/CSS/JS) into the map via `MacroElement`
   - Add sliders for key parameters. Each scoring dimension in `src/telttur/scoring/` has its own enable/disable flag and thresholds — these are natural candidates for controls:
     ```yaml
     map:
       interactive_controls:
         - scoring.cabin_density.enabled
         - scoring.accessibility.thresholds.poor
         - min_lake_area_m2
     ```
   - Store lake scoring data as a JSON object in the HTML (per-dimension score columns are already present on each lake feature)
   - Write JS to recompute composite scores (min of enabled dimensions) and update marker colors on slider/toggle change

3. **If not feasible with Folium**, document alternative approaches for a future task:
   - **Leaflet + vanilla JS**: Generate the map directly with Leaflet instead of Folium, embed scoring data as JSON, add slider controls with full JS interactivity
   - **Dash / Streamlit**: Python-based dashboards with reactive widgets — requires a running server
   - **deck.gl / kepler.gl**: High-performance WebGL map frameworks with built-in filter/slider widgets — better for large datasets, but steeper learning curve
   - **Observable / D3**: Notebook-style reactive documents, good for exploration

4. **Implement the chosen approach** or create a proof-of-concept for the recommended path.

## Acceptance Criteria
- [ ] Users can adjust at least 2 scoring parameters in the browser
- [ ] Lake colors/scores update dynamically when parameters change
- [ ] The set of exposed controls is configurable via config
- [ ] The map remains a static HTML file (no server required)
- [ ] If Folium proves insufficient, alternatives are documented with trade-offs
