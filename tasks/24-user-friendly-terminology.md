# Task 24 – User-friendly terminology and lake names in popups

## Goal

1. Rewrite user-facing labels and descriptions to speak to **a hiker looking for a nice place to camp**, not a developer inspecting data fields.
2. Show the **lake name** prominently at the top of popups when available.

## Current issues

- Labels like "Cabin density", "AR5 land use score", "building_density", "industrial_distance_m" are technical/developer-oriented.
- The popup table mixes scoring and raw data without clear hierarchy.
- Lake names are exported in the data (`name` field) but many are `null`. When present, they should be the popup headline.

## Proposed terminology changes

| Current label | Proposed label (EN) | Proposed label (NO) |
|---|---|---|
| Tentability | Camping suitability | Egnethet for telting |
| Cabin density | Seclusion | Avsidesliggenhet |
| Accessibility | Hiking distance | Turavstand |
| Land use (AR5) | Nature proximity | Nærhet til natur |
| Fishing | Fishing | Fiske |
| Building density | Nearby buildings | Bygninger i nærheten |
| Road distance | Distance to road | Avstand til vei |
| Industrial dist. | Distance to industry | Avstand til industri |
| Residential dist. | Distance to housing | Avstand til bebyggelse |
| Fish species | Fish species | Fiskearter |
| Min lake area | Minimum lake size | Minste innsjøstørrelse |

These should be integrated with the i18n system from task 24.

## Popup layout

```
┌────────────────────────────────┐
│ Storvatnet                     │  ← lake name (bold, larger)
│ ──────────────────────────     │
│ Camping suitability  [Good]    │  ← composite score badge
│ Seclusion            [Excellent]│
│ Hiking distance      [Good]    │
│ Nature proximity     [Fair]    │
│ Fishing              [Poor]    │
│ ──────────────────────────     │
│ Area: 4.5 ha                   │
│ Distance to road: 850 m        │
│ Nearby buildings: 0.02         │
│ Fish species: 3                │
└────────────────────────────────┘
```

- Lake name at top (if available), bold, slightly larger font.
- If name is `null`, omit the name row entirely (don't show "null" or "Unknown").
- Composite score first, then individual dimension scores, then details.

## Files to modify

- [web/app.js](../web/app.js) — `buildPopup()`, label strings, `LEVEL_NAMES`
- [web/style.css](../web/style.css) — popup name styling

## Dependencies

- Task 24 (i18n): terminology changes should use the translation system. If done before task 24, use English labels and mark strings for later extraction.

## Acceptance criteria

- All user-facing labels are hiker-friendly, not developer-oriented.
- Lake name displayed at the top of the popup when available.
- No "null" or empty name shown when name is unavailable.
- Detail rows use human-readable labels.
