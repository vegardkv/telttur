# Task 46 – Repo-wide fail-fast data audit

## Objective

The pipeline must **fail the build whenever a data source it depends on is missing or
unfetchable**, rather than silently skipping a dimension or substituting empty/default
data. A partial map is worse than a failed build: the gap is invisible downstream (the
frontend just shows weaker/absent scores with no signal that data was lost). This policy is
now stated in `CLAUDE.md` → Design Principles ("Fail fast on missing data"); this task is to
**audit the whole repo for consistency and fix the violations**.

Task 45 (Entur transit) already follows the policy — `load_transit_stops` raises and the
orchestrator no longer wraps it in a best-effort `try/except`. Use it as the reference shape.

## The distinction to apply

For every data-loading / scoring path, classify it as one of:

1. **Hard dependency** — a download/parse/extract that, on failure, must `raise` and abort
   the build. (Most network fetches.)
2. **Intentional source fallback** — switching to an alternative *source* by design (e.g.
   AR5 WFS → N50). Acceptable, **but the fallback path must itself fail hard** if it also
   fails; it must never collapse to empty data.
3. **Legitimately empty result** — a valid region that genuinely contains zero features
   (e.g. a bbox with no buildings). **Not** an error; leave as-is.

The audit's job is to make sure every `.empty` branch and every `except` is deliberately in
category 2 or 3, and that everything else is category 1.

## Spots to review (non-exhaustive — grep `except`, `.empty`, `fallback`, `WARNING`)

- **`download.py:82`** — fylke-bounds API failure prints a *warning* and uses a hardcoded
  bbox. Borderline: the hardcoded fallback is real static data, so arguably category 2, but
  it's currently a silent warning. Decide and document.
- **`scoring/__init__.py:61`** — `if buildings.empty:` → every lake gets zero building
  density. Is empty because the N50 building layer **failed to load** (category 1, should
  fail) or because the region truly has no buildings (category 3)? Distinguish the two:
  a failed/absent layer read must raise; a genuinely empty result may pass.
- **`scoring/ar5_land_use.py`** — the WFS→N50 fallback (category 2). Verify that when the
  N50 fallback *also* fails/empties, it raises rather than handing back empty polygons that
  silently become `inf` distances (lines 247–259). Confirm the AUTO chain can't end in
  silent emptiness.
- **`scoring/accessibility.py:46`** — empty `origins` → `inf`/`0`. For roads, decide whether
  "no drivable roads in the whole region" is a real failure or a tolerable edge.
- **`roads.py:108,124`** — empty-roads handling.
- **`scoring/fishing.py`** — download already raises (good); the empty-observations → 0
  path is category 3 (fine). Confirm.
- **`restrictions.py`** (task 44 drinking-water WMS) — confirm WMS/render failures raise
  rather than flagging zero lakes silently.
- **`elevation.py`** — DEM download already raises on failure (good); confirm no silent
  nodata-substitution masks a missing tile.

## Approach

1. Walk each module's data-loading and scoring entry points; tag every `except` / `.empty`
   branch with category 1/2/3 (a short comment in code is fine).
2. Convert category-1 silent paths to raise a clear `RuntimeError` naming the source.
3. For category-2 fallbacks, ensure the terminal fallback raises on failure.
4. Leave category-3 paths, but add a one-line comment noting *why* empty is valid there, so
   the intent is explicit for the next reader.
5. Consider a tiny shared helper (e.g. `require_nonempty(gdf, source_name)`) only if it
   removes real duplication — DRY/KISS; don't add an abstraction for three call sites.

## Notes / constraints
- Don't change the *intentional* AR5 WFS→N50 fallback behaviour; only harden its failure end.
- Keep error messages actionable (name the dataset + the cache/URL), matching the existing
  `RuntimeError(f"Failed to download ...")` style in `elevation.py` / `fishing.py`.
- No new config knobs (CLAUDE.md: lean config).

## Acceptance criteria
- [x] Every data-loading / scoring path is classified (1 hard / 2 fallback / 3 empty-ok),
      with category-3 paths commented as to why empty is valid.
- [x] All category-1 failures raise and abort the build; none silently degrade the map.
- [x] Intentional source fallbacks (AR5) still work but fail hard at their terminal path.
- [x] CLAUDE.md "Fail fast on missing data" principle matches the implemented behaviour.
- [x] `uv run ruff check`, `uv run ruff format`, `uv run ty check` all pass.

## Outcome

Audit applied across the pipeline. Category-1 silent paths converted to raise:
- `download.py` — `_order_fylke` / `_download_and_extract` now raise on unavailable
  fylke, missing format, order failure, not-ready file, or download error (were warn +
  skip, producing a partial map). The fylke-bounds API fall-through is documented as a
  deliberate category-2 fallback to the complete built-in `FYLKE_BOUNDS`.
- `roads.py`, `lakes.py`, `cabin_density.py` — "no road/lake/building *layer* found in
  any N50 dataset" now raises (corrupt/incomplete download), distinct from a valid region
  with zero features after clipping (category 3).
- `ar5_land_use.py` — the N50 fallback (terminal end of the AUTO chain) raises when no
  arealdekke layer exists, so the chain can't collapse to silent `inf` distances.

Category-3 empty branches (accessibility origins, fishing observations, AR5 empty zones,
empty roads styling, empty-lakes restriction guard) left as-is with comments explaining
why empty is the correct, accurate result there.
