# Task 25 – Internationalization (Norwegian / English)

## Goal

Support two languages — **Norwegian (Bokmål)** and **English** — across all user-facing text in the web app. The user should be able to switch languages via a toggle.

## Scope

All user-visible strings:
- Control panel labels, dimension names, info descriptions
- Popup field labels (score names, detail labels)
- Legend text
- Level names (Terrible/Poor/Fair/Good/Excellent → Forferdelig/Dårlig/Middels/Bra/Utmerket)
- Page title
- Any "no data" or error messages

## Design

### Translation dictionary approach

Keep a simple `i18n` object in a separate file or at the top of `app.js`:

```js
const I18N = {
  en: {
    title: "Telttur – Norwegian Camping Suitability Map",
    scoring: "Scoring",
    cabin_density: "Cabin density",
    accessibility: "Accessibility",
    land_use: "Land use (AR5)",
    fishing: "Fishing",
    level_1: "Terrible",
    level_2: "Poor",
    level_3: "Fair",
    level_4: "Good",
    level_5: "Excellent",
    // ... etc.
  },
  no: {
    title: "Telttur – Kart over teltturer i Norge",
    scoring: "Poengberegning",
    cabin_density: "Hyttetetthet",
    accessibility: "Tilgjengelighet",
    land_use: "Arealbruk (AR5)",
    fishing: "Fiske",
    level_1: "Forferdelig",
    level_2: "Dårlig",
    level_3: "Middels",
    level_4: "Bra",
    level_5: "Utmerket",
    // ... etc.
  }
};
```

### Language switcher

- A small toggle (e.g. 🇬🇧/🇳🇴 flags or "EN | NO" text buttons) in the top-left or near the control panel.
- Default language: detect from `navigator.language` (default to Norwegian if `nb`, `nn`, or `no`, else English).
- Store preference in `localStorage`.

### Implementation approach

1. Create a `t(key)` function that returns the string for the current language.
2. Replace all hardcoded strings with `t("key")` calls.
3. When language switches, rebuild dynamic content (controls, legend) and update the page title.
4. Popups are rebuilt on open (after task 20), so they'll pick up the current language automatically.

## Files to modify

- [web/app.js](../web/app.js) — translation function, string replacement, language switcher
- [web/index.html](../web/index.html) — language toggle element (if static)
- [web/style.css](../web/style.css) — language toggle styling

## Dependencies

- Task 20 (popup rebuild) should be done first so popups automatically use the current language.

## Acceptance criteria

- All user-facing text renders in the selected language.
- Language toggle visible and functional.
- Language preference persists across page reloads (localStorage).
- Default language auto-detected from browser settings.
