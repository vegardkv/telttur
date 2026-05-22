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
