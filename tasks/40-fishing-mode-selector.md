# Task 40 – Fishing mode selector

Round 10 item: a mode selector for the fishing dimension with two ways of combining
the user's selected fish species.

## Objective

Today the fishing score is a single graded function: the *fraction* of desired prized
genera present at the lake, mapped to levels 1–5 (`scoreFishing` in `web/app.js`,
lines ~238). Give the user a choice between two interpretations:

- **"Hvilken som helst fisk" (Any is good)** — OR semantics. If **any** selected genus
  is present → **Utmerket (5)**. Otherwise → **Elendig (1)**.
- **"Jo flere jo bedre" (More is merrier)** — three-level semantics:
  - **all** selected genera present → **Utmerket (5)**
  - **none** present → **Elendig (1)**
  - one or more present but at least one missing → **Middels (3)**

"More is merrier" is intentionally a 3-level collapse of the current behaviour, not the
5-level fraction. The graded fraction logic can be removed (no longer used by either
mode) unless we decide to keep it as a third mode — default is to **replace** it.

## Context

- Scoring is JS-only (no Python change). `scoreFishing(generaMask, desiredMask)` lives
  in `web/app.js` (~238) and is called from `computeScores` (~308).
- The fishing card UI is built in `buildControls()` (~668): a multi-select dropdown of
  genera (`tt-fg-${g.code}` checkboxes). The mode selector goes in this card.
- Control state is gathered in `readControlState` (~254), which already builds
  `fishingMask` from the checkboxes — add the selected mode there.

## Steps

1. **UI** — add a mode selector inside the fishing card body (`tt-fishing-body`),
   above the genera dropdown. Use the noUiSlider-consistent styling guidance, but a
   simple two-option segmented control / radio pair is fine here (it's a discrete
   choice, not a range). Give it a stable id (e.g. `tt-fish-mode`) and i18n labels.
   - New i18n keys (Norwegian only — English was removed in task 34): e.g.
     `fish_mode_label`, `fish_mode_any`, `fish_mode_all`.

2. **Read state** — in `readControlState`, read the selected mode (`"any"` | `"all"`)
   into the returned `cs` object (e.g. `cs.fishingMode`).

3. **Scoring** — rewrite `scoreFishing(generaMask, desiredMask, mode)`:
   ```js
   function scoreFishing(generaMask, desiredMask, mode) {
     if (!desiredMask) return null;            // no genera selected → skip dimension
     const matched = popcount(generaMask & desiredMask);
     const wanted  = popcount(desiredMask);
     if (mode === "any") return matched > 0 ? 5 : 1;
     // "all" / more-is-merrier
     if (matched === 0) return 1;
     return matched === wanted ? 5 : 3;
   }
   ```
   Update the call site in `computeScores` to pass `cs.fishingMode`. Remove `popcount`
   only if it becomes unused (it's still used here, so keep it).

4. **Popup / info** — update the fishing info tooltip (`fishing_info`) to explain the
   two modes. The genera list shown in the popup (line ~400) is unaffected.

5. **Default mode** — default to **"any"** (broadest, most forgiving) unless the user
   prefers "all". Confirm if unsure.

## Acceptance criteria

- [ ] Fishing card shows a two-option mode selector, styled consistently.
- [ ] "Any" mode: 5 if at least one selected species present, else 1.
- [ ] "All/more is merrier" mode: 5 if all present, 3 if some present, 1 if none.
- [ ] Switching mode (or genera) re-colours markers on slider release.
- [ ] Fishing info tooltip describes both modes.
- [ ] No leftover dead code from the old fraction logic.
