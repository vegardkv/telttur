# Task 33 – Round 5 polish

## Goal

Address five remaining UI polish items to improve visual consistency and usability.

---

## 1. Unify slider styles

**Problem:** Native `<input type="range">` sliders and noUiSlider range sliders have slightly different visual styles despite attempts to align them. The native sliders lack a filled/connect region, and minor sizing/spacing differences remain.

**Fix:** Replace all native `<input type="range">` sliders (cabin density, AR5 residential buffer, AR5 industrial buffer) with noUiSlider instances (single-handle mode). This eliminates the two-code-path styling problem entirely — every slider uses the same library and the same CSS.

**Files:** `web/app.js`, `web/style.css`

**Details:**
- The dimension cards for cabin density (`#tt-ct`), AR5 residential (`#tt-ar5r`), and AR5 industrial (`#tt-ar5i`) currently render `<input type="range">`.
- Convert each to a `<div>` target + `noUiSlider.create(...)` with a single handle, matching the pattern already used by the accessibility and lake-size sliders.
- Once no native range inputs remain, the `input[type="range"]` CSS rules can be removed from `style.css`.

---

## 2. Increase lake size upper bound and lower initial minimum

**Problem:** The lake size slider caps at 10 km² (10 000 000 m²). Some Norwegian lakes are significantly larger. The initial minimum value (`cfg.min_lake_area_m2`, often 50 000 m² for the national config) means many small lakes are loaded on startup, hurting initial performance.

**Fix:**
- Raise the slider upper bound from `10 000 000` to `50 000 000` m² (50 km²). Adjust the non-linear range steps accordingly to keep the lower end fine-grained.
- Set the **initial lower handle** to a higher default (e.g. `100 000` m²) so fewer markers render on first load. This is the slider start value, not the config `min_lake_area_m2` (which controls the pipeline export). Update only `app.js`.

**Files:** `web/app.js`

---

## 3. Cap cabin density slider at 0.15

**Problem:** The cabin density slider currently reads its max from `cd.slider_max` in config, which defaults to `0.5`. In practice values above ~0.15 are meaningless — virtually all lakes already score Excellent at that threshold.

**Fix:** Change the default `slider_max` in `InteractiveCabinDensitySlider` from `0.5` to `0.15`. This makes the slider more precise in the useful range.

**Files:** `src/telttur/config.py`

---

## 4. Set accessibility distance minimum to 0

**Problem:** The accessibility range slider lower bound starts at the config default `min_m = 200`. Users should be able to drag the lower handle all the way to 0 (i.e. "right next to a road is fine").

**Fix:** Change the default `min_m` in `InteractiveAccessibilityRange` from `200.0` to `0.0`.

**Files:** `src/telttur/config.py`

---

## 5. Multi-select dropdown for fish species

**Problem:** Fish genera are shown as individual checkboxes in a list inside the fishing dimension card. With 8 genera the list takes a lot of vertical space.

**Fix:** Replace the checkbox list with a compact multi-select dropdown. Implementation options (pick one):

- **Option A – Custom dropdown with checkboxes.** Render a styled `<button>` showing the count/summary of selected genera. Clicking it toggles a small absolutely-positioned panel with the checkboxes. This keeps the interaction model the same (toggle individual genera) but collapses the list.
- **Option B – Use a lightweight library** (e.g. Choices.js via CDN, ~5 KB gzipped) that provides a multi-select dropdown out of the box. Evaluate whether the dependency is worth it.

Whichever approach is chosen:
- The underlying bitmask logic (`fishingMask |= (1 << g.code)`) stays the same.
- The "select all / deselect all" toggle should still be available.
- The collapsed state should show a summary like "5 of 8 selected" or list the selected names if few enough.

**Files:** `web/app.js`, `web/style.css`, possibly `web/index.html`

---

## Verification

- Visually confirm all sliders look identical (same track height, handle size, colours).
- Drag lake-size slider to full range and verify 50 km² upper bound.
- Confirm cabin density slider max is 0.15.
- Confirm accessibility lower handle can reach 0.
- Confirm fish species dropdown collapses into a compact control and selecting/deselecting genera still filters lakes correctly.
- Run `uv run ruff check .` and `uv run ruff format --check .` to ensure Python changes pass linting.
- Open the map in a browser and verify no regressions in popup scores or interactivity.
