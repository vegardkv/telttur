# Task 17: Colored Scoring Labels in Popup

## Objective
Show per-dimension scores in the lake popup with colour-coded labels matching the legend colours. This makes it immediately obvious why a lake received its composite score.

## Context
Currently, popups show dimension scores as plain text (e.g. "Cabin density: Good"). Users have difficulty interpreting which dimension is dragging the composite score down. Adding colour indicators makes the scoring breakdown intuitive at a glance.

## Steps

1. **Update popup HTML generation** in `_add_lake_markers()` and the GeoJson popup path in `src/telttur/map_generator.py`:
   - For each scoring field in the popup, wrap the value in a coloured badge/pill:
     ```html
     <td><span style="background:#1a9850;color:white;padding:1px 6px;border-radius:3px;font-size:11px">Excellent</span></td>
     ```
   - Use the existing `LEVEL_COLORS` mapping from `src/telttur/scoring/__init__.py`

2. **Identify score columns**:
   - Score columns are those returned by `get_scoring_popup_fields()` where the value matches a tentability level name (Terrible/Poor/Fair/Good/Excellent)
   - The composite "Tentability" field should also be colour-coded

3. **Handle the marker mode**:
   - In marker mode, popup HTML is built manually in the `for _, row` loop — add inline colour styling there
   - Determine text colour (white for dark backgrounds, black for light like `#fee08b`)

4. **Handle the polygon mode**:
   - `GeoJsonPopup` uses field values directly — this mode may not support inline HTML easily
   - If not feasible for polygon mode without significant refactoring, skip it (marker mode is the primary display for the first viable model)

## Acceptance Criteria
- [ ] Scoring fields in marker popups display with colour-coded badges
- [ ] Colours match the legend (Excellent=green, Terrible=red)
- [ ] Composite tentability field is also colour-coded
- [ ] Text remains readable on all badge colours
