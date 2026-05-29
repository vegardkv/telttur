# Task 34 – Round 7 polish

Five targeted changes to the web frontend and one pipeline config tweak.

---

## 1. Merge legend into criteria pane

**Goal:** Remove the standalone `#tt-legend` floating box; embed the swatch legend inside the criteria/controls panel.

**Changes – `web/app.js`:**
- Remove the `buildLegend()` function entirely.
- Remove the `buildLegend(data)` calls in `initMap()` and `rebuildUI()`.
- At the bottom of `buildControls()`, after the lake size filter section, append a legend block directly into `#tt-body`:
  - A short section heading (use `t("legend_suitability")` – one line, no second title).
  - Five swatch rows (level 5 → 1), same markup as the current legend (`tt-legend-row` / `tt-legend-swatch`).

**Changes – `web/style.css`:**
- Remove the `#tt-legend` rule block.
- The swatch/row classes (`tt-legend-row`, `tt-legend-swatch`) are shared; keep them, but no longer need positioning rules for `#tt-legend`.

---

## 2. New defaults

### 2a. Lake size slider starts at 0

In `buildControls()` the noUiSlider for lake size currently starts at `[100000, 50000000]`.
Change the `start` to `[0, 50000000]`.

The initial label for `tt-ls-min-val` in the HTML template already uses `minArea`
from config (`formatArea(cfg.min_lake_area_m2 || 0)`), but the noUiSlider `update`
event fires on init and overwrites it anyway — no separate label fix needed.

### 2b. Cabin density and fishing start unchecked (and collapsed)

`buildDimCard()` currently always renders `<input type="checkbox" id="${id}" checked>`.

- Add a `defaultChecked = true` parameter.
- Pass `defaultChecked = false` for the cabin density and fishing cards.
- When `defaultChecked` is false, omit the `checked` attribute and also set
  the card body `display: none` in the initial HTML (same as when a user
  unchecks — the toggle listener handles it, but on first render the body
  must already be hidden so no flicker occurs).

No change needed to `readControlState`; it already reads the live checkbox state.

---

## 3. Reduce Norway min lake size by 50%

**File: `config_norway.yaml`**

```yaml
min_lake_area_m2: 10000   →   min_lake_area_m2: 5000
```

This affects only the Python pipeline (the `generate` step). The web frontend
reads whatever is in `data.js`. Re-run `uv run telttur generate --config config_norway.yaml`
to apply.

---

## 4. Remove English

The app is Norwegian-only going forward. Removing English simplifies the code and
eliminates the language-switcher UI element.

**`web/app.js`:**
- Delete the entire `en: { … }` block from `I18N`.
- Delete `_detectLang()`, `setLang()`, and the `_lang` variable.
- Simplify `t(key)` to: `return I18N.no[key] ?? key;`
- In `_start()` and `rebuildUI()`, remove the `document.documentElement.lang` line
  (it's now set statically in HTML).
- In `buildControls()`, remove the language-switcher `<div id="tt-lang-switcher">` block
  and both `addEventListener` calls for `setLang`.
- In `rebuildUI()`, remove the `oldLang` / `oldLang.remove()` stanza.

**`web/index.html`:**
- Change `<html lang="en">` → `<html lang="nb">`.

**`web/style.css`:**
- Remove the `#tt-lang-switcher`, `.tt-lang-btn`, and `.tt-lang-active` rule blocks.

---

## 5. Re-color on slider release, not during drag

**Goal:** `teltturUpdate()` should fire only when the user *releases* a slider handle
(`change` event), not continuously while dragging (`update` event). Label display
should still update live.

noUiSlider events used:
- `update` — fires on every move (use only for label updates)
- `change` — fires on mouseup/touchend (use for `teltturUpdate`)

**For each slider, split the handler:**

```js
// Before (all-in-one):
slider.on("update", (values) => {
  labelEl.textContent = format(values[0]);
  teltturUpdate(_ttCfg);
});

// After (split):
slider.on("update", (values) => {
  labelEl.textContent = format(values[0]);
});
slider.on("change", () => teltturUpdate(_ttCfg));
```

Apply to all five sliders: `_ctSlider`, `_ar5ResSlider`, `_ar5IndSlider`,
`_arSlider`, `_lakeSizeSlider`.

The `change` callback doesn't need the `values` argument since
`teltturUpdate` reads slider values itself via `_arSliderMin()` etc.
