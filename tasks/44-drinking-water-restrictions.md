# Task 44: Drinking-water lakes & a restrictions concept

## Objective

Surface lakes that are **drinking-water sources** (`drikkevannskilde`). These typically
carry legal restrictions on fishing, swimming and camping, so a user planning to tent
nearby wants to know. First version:

1. A **filter toggle** (sibling of the lake-size and "minimum egnethet" filters) that
   hides drinking-water lakes. **Default: include them** (toggle off = show everything).
2. The lake **popup** states whether the lake is a drinking-water source.

Where it's cheap to do so, model this as a **general "restriction" flag** rather than a
one-off boolean, so future restriction types (e.g. nature reserves, no-camping zones)
slot in without a schema change. Don't over-build it though (CLAUDE.md: DRY/KISS) — one
bitmask field with one bit set today is the right amount of generality.

## Background — the hard part is the data

The pipeline currently has **no drinking-water source**. Lakes come from N50 Kartdata
(`lakes.py`), which to my knowledge carries no drinking-water attribute. So step one is
research, not code: find an authoritative dataset and decide how to join it to lakes.

Candidate Geonorge / public sources to investigate (verify before trusting any):
- **Beskyttede områder etter vannforskriften** (protected areas under the Water
  Framework Directive) — includes drinking-water protection zones (`drikkevann`).
- **Mattilsynet** drinking-water supply / source registers.
- **NVE Innsjødatabase** — richer per-lake attributes than N50; check for a
  drinking-water / `drikkevann` field.
- **Miljødirektoratet Naturbase** — for the later, generalized restriction types.

Join strategy to decide:
- If the source is **polygons** (protection zones): spatial intersect/overlap against
  the lake polygon. Beware that a protection zone is usually larger than the lake.
- If it's **per-lake attributes** keyed by a waterbody id/name: prefer an id/name join,
  falling back to a spatial join (same trade-off noted in task 42 for fishing).
- Coordinate/edge cases: a lake may be partly in a zone; pick a sensible threshold
  (any overlap → flagged is the simplest defensible rule for v1).

**Confirm the chosen source + join with a few hand-checked lakes** (pick a known
municipal drinking-water lake) before wiring it through.

## Suggested design

### Python side
1. **New module / extraction** (e.g. `restrictions.py`, or fold into `lakes.py` if the
   source is a lake attribute) that downloads (extend `download.py`) and loads the
   drinking-water dataset, then tags each lake.
2. **One new lake column** — a **restrictions bitmask** mirroring the existing
   `FISH_GENERA_MASK` pattern (`LakeCols`):
   ```python
   RESTRICTIONS_MASK = "restrictions_mask"   # bit 0 = drinking water (drikkevann)
   ```
   A bitmask (not a bool) is the lean generalization: new restriction types are new bits,
   no new columns, no data.js shape change. Define the bit meanings in one place shared
   with the export (a small `RESTRICTIONS` list of `{code, key}`, like `PRIZED_GENERA`).
3. **Export** — add `RESTRICTIONS_MASK` to `optional_cols` in `build_lake_data`
   (`data_export.py`), exported as `int` like the other masks. Add the restriction-bit
   definitions to the config block (`build_config_block`) so the frontend can label them,
   alongside `fishing.genera`.

### Frontend side (`web/app.js`, single file)
4. **Filter toggle** — new `tt-filter-section` next to the lake-size / min-score filters
   (built ~749–773). A checkbox is appropriate here (discrete on/off), styled to match.
   - i18n keys (Norwegian only — English was removed in task 34), e.g.
     `drinking_water_filter` ("Drikkevann"), `drinking_water_filter_hint`
     ("Skjul innsjøer som er drikkevannskilder").
   - No inline handlers — `addEventListener`; re-filter via `teltturUpdate` on change
     (match how the sliders call it).
5. **Read state** — in `readControlState` (~254–281) add e.g. `cs.hideDrinkingWater`.
6. **Filter logic** — in both marker-filter spots (~340–360 and ~541–545), hide the
   lake when `cs.hideDrinkingWater && (fields.restrictions_mask & DRINKING_WATER_BIT)`.
   This **hides** (like the area filter), not greys out (which the score filter does).
7. **Popup** — in `buildPopup` (~375+), add a detail row stating drinking-water status.
   Show a clear positive line when flagged (e.g. "Drikkevannskilde – restriksjoner kan
   gjelde"); decide whether to show anything when not a source (probably omit to keep the
   popup lean, matching how absent fields are skipped).
   - i18n: `drinking_water` label + a value string.

## Notes / constraints
- Keep `config.yaml` lean — only add inputs that are strictly required to fetch/locate
  the new dataset (CLAUDE.md). If the source needs no per-region ordering, no config knob.
- The restriction → "should this be hidden by default" question: **no**, per the user —
  default includes drinking-water lakes; the toggle is opt-in hiding.
- Bitmask labelling/strings live JS-side; Python exports the raw mask (consistent with
  fishing). Don't bake legal interpretation into the data — we flag "is a source", the
  text only says restrictions *may* apply.
- Data licensing/attribution: if a new Geonorge dataset is used, add it to the credits
  list (see task 29 / the credits block ~998).

## Acceptance criteria
- [ ] Lakes that are drinking-water sources are identified from an authoritative dataset,
      validated against a few hand-checked lakes.
- [ ] `data.js` carries a per-lake `restrictions_mask` (bit 0 = drinking water).
- [ ] A filter toggle hides drinking-water lakes; **default is to include** them.
- [ ] Toggling re-filters markers (consistent with existing filter behaviour).
- [ ] The popup states when a lake is a drinking-water source.
- [ ] New data source is attributed/licensed in the credits.
- [ ] `uv run ruff check`, `uv run ruff format`, `uv run ty check` clean.
