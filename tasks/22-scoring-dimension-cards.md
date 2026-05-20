# Task 22 – Scoring dimension cards with info buttons

## Goal

Redesign the control panel so each scoring dimension is presented as its own **card** containing:
1. A toggle (enable/disable checkbox)
2. The associated sliders/settings for that dimension
3. A small **info button** (ⓘ) that shows a tooltip or expandable description of what the dimension measures

Currently the panel has dimension checkboxes grouped at the top and sliders grouped below. This task merges them into per-dimension cards.

## Design

### Card layout (one per dimension)

```
┌─────────────────────────────────┐
│ [✓] Accessibility    ⓘ         │
│  Min: 200 m  ──●────── 10000   │
│  Max: 2000 m ────●──── 10000   │
└─────────────────────────────────┘
```

- **Header row**: checkbox toggle + dimension label + info icon
- **Body**: sliders and value displays (collapsed when toggled off)
- **Info tooltip**: on hover (desktop) or click (mobile), show a short description of what the dimension means for a hiker

### Info text per dimension

- **Cabin density**: "How isolated the area is from buildings and cabins. Lower density means a more secluded camping experience."
- **Accessibility**: "How far you need to walk from the nearest road. Set your preferred hiking distance range."
- **Land use (AR5)**: "Proximity to residential and industrial areas. Greater distance from developed areas is preferred."
- **Fishing**: "Fishing opportunities based on known fish species in the lake."

### Behaviour

- When a dimension is toggled off, its sliders should be hidden or greyed out (visually indicate they are inactive).
- The card should have a subtle border/background to visually separate dimensions.
- Keep the panel collapsible (existing toggle button).

## Files to modify

- [web/app.js](../web/app.js) — `buildControls()` rewrite
- [web/style.css](../web/style.css) — card styles, info tooltip styles

## Acceptance criteria

- Each scoring dimension has its own visually distinct card.
- Toggling a dimension off hides/disables its sliders.
- Info button shows a helpful description on hover or click.
- Panel remains collapsible.
- No functional regression in scoring.
