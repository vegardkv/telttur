# Task 31 – Evaluate lightweight UI library

## Goal

Evaluate lightweight CSS/UI libraries that could improve the visual consistency and polish of the control panel without introducing a build step or heavy framework.

## Constraints

- **No build/compilation step** — must work via CDN `<link>` / `<script>` tags
- **No framework** — no React, Vue, Svelte, etc.
- **Lightweight** — small footprint, ideally < 10 KB gzipped for CSS
- **Minimal JS** — prefer CSS-only or CSS-first libraries; any JS should be optional
- Must not conflict with Leaflet's CSS

## Candidates to evaluate

### CSS-only / minimal libraries

1. **Pico CSS** (~10 KB gzipped) — classless CSS framework, styles semantic HTML automatically. Minimal effort to adopt.
2. **Water.css** (~2 KB) — classless, very minimal. May be too basic.
3. **MVP.css** (~6 KB) — classless with a clean look.
4. **Simple.css** (~4 KB) — classless, accessible.

### Utility / component libraries

5. **Milligram** (~2 KB) — lightweight CSS framework with a grid and basic components.
6. **Sakura** (~1 KB) — classless, extremely minimal.

### Slightly heavier options (still no build step)

7. **Bulma** (~25 KB gzipped) — CSS-only, no JS, well-documented. Has form controls, cards, and modals.
8. **UIkit** (~30 KB) — more comprehensive, includes JS components, available via CDN.

## Evaluation criteria

For each candidate, assess:
1. **Visual quality** of form controls (sliders, checkboxes, buttons)
2. **Card/panel** components (for scoring dimension cards)
3. **Tooltip** support (for info buttons)
4. **Compatibility** with Leaflet and noUiSlider
5. **File size**
6. **Ease of adoption** — how much existing HTML/CSS needs to change
7. **Code reduction** — how much custom CSS and inline JS can be eliminated by leveraging the library's built-in styling and components. Assess the impact on readability and ease of maintenance.

## Output

A recommendation with:
- Which library (if any) to adopt
- Proof-of-concept: apply it to the control panel to demonstrate the visual improvement
- List of HTML/CSS changes required
- Any conflicts or caveats discovered

## Decision

This is an **evaluation task**. The implementer should produce a recommendation and a small proof-of-concept, then the developer decides whether to proceed with full adoption.

---

## Evaluation Results

### Actual measured sizes (gzipped)

| Library | Minified | Gzipped | Type | Scoping |
|---------|----------|---------|------|---------|
| Milligram | 9 KB | 2.3 KB | Class-based | Inherent (opt-in classes) |
| MVP.css | 10 KB | 2.7 KB | Classless | None |
| Simple.css | 9 KB | 2.8 KB | Classless | None |
| Water.css | 23 KB | 3.6 KB | Classless | None |
| **Pico CSS conditional** | **87 KB** | **12 KB** | Classless (scoped) | `.pico` class |
| *Current custom CSS* | *8.9 KB* | *2 KB* | — | — |

Bulma (~25 KB gzipped) and UIkit (~30 KB gzipped) were excluded — too heavy.

### Evaluation matrix

| Criterion | Pico (conditional) | Simple.css | Water.css | MVP.css | Milligram |
|-----------|-------------------|------------|-----------|---------|-----------|
| Form controls (sliders, checkboxes, buttons) | Excellent | Good | Fair | Fair | Fair |
| Card/panel components | None (use `<article>`) | None | None | None | None |
| Tooltip support | None | None | None | None | None |
| **Leaflet compatibility** | **Good** (`.pico` scoping) | **Poor** (global) | **Poor** (global) | **Poor** (global) | Good (opt-in) |
| File size | 12 KB gz (over budget) | 2.8 KB gz | 3.6 KB gz | 2.7 KB gz | 2.3 KB gz |
| Ease of adoption | Medium | Easy (but conflicts) | Easy (but conflicts) | Easy (but conflicts) | Hard (add classes to all JS) |
| Code reduction | ~80-100 lines saved | ~60 lines | ~40 lines | ~50 lines | ~20 lines |

### Key finding: scoping is the dealbreaker

Leaflet creates its own `<a>`, `<button>`, `<input>`, and `<span>` elements for zoom controls, attribution, popups, and layer controls. **Classless libraries** (Simple.css, Water.css, MVP.css) style all HTML elements globally, causing conflicts:

- Zoom buttons restyled (Leaflet uses `<a>` elements)
- Attribution links change appearance
- Popup fonts/spacing altered
- Layer control checkboxes restyled

Only **Pico CSS conditional** supports scoping via `.pico` class containers. **Milligram** is class-based (opt-in), but requires adding classes to every generated HTML element in `app.js` — very invasive.

### Proof-of-concept

A PoC has been applied to the working tree (easily revertible with `git checkout`):

**Changes made:**
1. `web/index.html` — added Pico CSS conditional CDN link
2. `web/app.js` — added `.pico` class to 5 container elements (`#tt-controls`, `#tt-legend`, `#tt-footer`, `#tt-credits-dialog`, `#tt-lang-switcher`)
3. `web/style.css` — added ~30 lines of CSS variable overrides to tighten Pico's default spacing for our compact panel UI

**What improved:**
- Checkboxes get a polished toggle-style appearance
- Buttons have smoother hover/focus states
- The `<dialog>` element gets better backdrop and transition styling
- Typography uses `system-ui` font stack (more modern)

**What broke or needed overrides:**
- Pico adds generous `margin-bottom` to all form elements → had to zero it out
- Pico's default spacing is designed for full-page layouts, not compact panels → had to override CSS custom properties
- Range input styling conflicts with our existing custom styles and noUiSlider
- The `:root` reset changes fonts globally (even outside `.pico` containers)

### Recommendation: **Do not adopt a library**

**Rationale:**
1. **Size vs. value:** Pico CSS conditional adds 12 KB gzipped (6× our entire current CSS) for marginal visual improvement to a control panel that already looks clean.
2. **Overrides negate the benefit:** ~30 lines of overrides were needed just for the PoC. Full adoption would require more, approaching the point where we're fighting the library more than benefiting from it.
3. **No card/tooltip components:** None of the candidates provide the card or tooltip components our UI already has in custom CSS. We'd still maintain all that code.
4. **None of the classless options are Leaflet-safe.** The scoped option (Pico conditional) is the only viable one, and it's the heaviest.
5. **Better ROI from targeted improvements:** Adding 15-20 lines of custom CSS could achieve the same visual polish (styled checkboxes, button hover states, smooth transitions) without any dependency.

**If you want the polished checkbox/button look without a library**, consider adding these ~15 lines to `style.css`:

```css
/* Polished checkbox appearance */
#tt-body input[type="checkbox"] {
  accent-color: #555;
  width: 15px;
  height: 15px;
}

/* Button hover transitions */
.tt-lang-btn, #tt-toggle-btn, #tt-credits-btn {
  transition: background 0.15s, color 0.15s;
}

/* Dialog open/close transition */
#tt-credits-dialog {
  animation: fadeIn 0.15s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

To revert the PoC changes: `git checkout web/`
