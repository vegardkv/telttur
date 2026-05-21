# Task 30 – JavaScript code review (DRY, SoC, KISS)

## Goal

Review `web/app.js` for adherence to fundamental software engineering principles and refactor where warranted.

## Scope

Audit the ~800-line `app.js` file for:

### DRY (Don't Repeat Yourself)

- Repeated patterns in slider/control construction (each dimension card has similar boilerplate)
- Duplicated scoring function structures (`scoreAccess`, `scoreCabin`, `scoreAr5One` follow a similar threshold-based pattern)
- Repeated DOM element creation patterns

### Separation of Concerns (SoC)

- Consider whether the single `app.js` file should be split into logical modules (e.g. `i18n.js`, `scoring.js`, `controls.js`, `map.js`)
- Inline `oninput`/`onchange` handlers mix HTML generation with behaviour — consider using `addEventListener` instead
- Global mutable state (`_ttCfg`, `_ttData`, `_arSlider`, `allMarkers`, etc.) — evaluate whether this can be better encapsulated

### KISS (Keep It Simple)

- Bitmask approach for fishing genera — is this the simplest way to handle a small set of checkboxes?
- Are there over-engineered abstractions or unnecessarily complex patterns?

## Guidelines

- This is a **review task** — produce a list of findings with specific refactoring suggestions
- Prioritise changes by impact: high-impact improvements first
- Do **not** introduce a build step, bundler, or framework
- Do **not** split into modules if it complicates the no-build-step constraint (ES modules with `type="module"` in the script tag are acceptable if they work without a server for local development)
- Keep changes pragmatic — the app is ~800 lines, not a large codebase

## Output

A list of concrete refactoring suggestions, each with:
1. What the issue is
2. Where it occurs (function/line)
3. Suggested fix
4. Priority (high/medium/low)

Implement high-priority fixes directly. Document medium/low as future improvements.

## Files to review

- [web/app.js](../web/app.js)
- [web/style.css](../web/style.css) — for any CSS that could be simplified
