# Task 35 – Round 8 cleanup

Pure dead-code removal round. No behaviour changes — every step should leave
`uv run telttur generate --config config.yaml` and the web app working
exactly as they do today. The goal is long-term maintainability: fewer knobs
that nobody turns, fewer code paths that nobody exercises.

After each step: run `uv run ruff check`, `uv run ty check`, regenerate
`config.yaml` once, and open `output/data.js` in the browser.

---

## 1. Trim `src/telttur/main.py` to a single command

Only `generate` is used in practice. Remove the unused subcommands so the CLI
surface area matches the actual workflow.

**Remove the following commands entirely:**
- `download` (`main.py:189–205`) — only ever used as a debugging step.
- `inspect` (`main.py:208–219`) — ad-hoc developer tool, not a user-facing flow.
- `sample` (`main.py:222–249`) — the profile system is also removed in step 2;
  with no profiles there is nothing to sample.

**Collapse the `click.group()` into a single command:**
- Replace `@click.group()` + `@cli.command()` with a single top-level
  `@click.command()` named `cli` (or rename the entry point so users still
  type `uv run telttur generate`).
- Decide: keep `generate` as the subcommand name (preserves muscle memory and
  CLAUDE.md instructions) or flatten to `uv run telttur`. Recommended: keep
  `generate` so existing docs and configs don't churn — i.e. `@cli.group()`
  with one child command.

**Update `pyproject.toml`** if any entry-point or script references the
removed commands.

**Update CLAUDE.md** — remove the "Other CLI commands (rarely used)" block
under *Common Commands*.

---

## 2. Remove `--skip-download` from `generate`

In `main.py:68` and the body at `main.py:100–116`, drop the flag and the
branch that searches for existing `.gdb` files. Always run `download_n50`.

Rationale: the download step is idempotent on the HTTP cache, so the flag
only saved a few seconds at the cost of an extra code path and the
`ClickException` branch ("Run without --skip-download first").

**Also remove the mention in CLAUDE.md** (`# Reuse cached data` example).

---

## 3. Remove the `Profile` system

With `sample` gone and configs being the canonical entry point, the
`Profile`/`build_profile_config`/`dump_config_yaml` machinery is dead.

**`src/telttur/config.py`:**
- Delete the `Profile` enum (`config.py:261–265`).
- Delete `build_profile_config()` (`config.py:267–313`).
- Delete `_convert_enums()` and `dump_config_yaml()` (`config.py:316–347`).

**`src/telttur/main.py`:**
- Remove the `--profile` option and the `if profile and config_path` guard
  (lines 62–67, 79–85). The `generate` command now takes `--config` only,
  defaulting to `config.yaml`.

**Imports:** remove `Profile`, `build_profile_config`, `dump_config_yaml`
from the `from telttur.config import …` line in `main.py:8`.

---

## 4. Audit and prune `src/telttur/config.py`

Many fields are either never read or always-true. Walk each field on the
`Config` and nested models and delete the ones that are dead. Use
`Grep` with the field name across `src/` to verify before removing.

**Confirmed dead (set in configs/profiles but never read in `src/telttur/`):**
- `lake_display_mode` (`config.py:192`) — only appears in `config.py` and
  YAML files; no consumer. Delete the field and remove it from the four
  `config_*.yaml` files.
- `buffer_distance_m` (`config.py:181`) — only printed at startup
  (`main.py:93`); never affects pipeline output. Delete field + the print.
- `landcover_mode` (`config.py:188`) — only printed at startup
  (`main.py:94`); the WMS overlay is now AR5-frontend-only and
  `landcover.py` does not reference it. Delete field + the print + the
  `Literal["wms", "vector", "disabled"]` import if it becomes unused.

**Probably dead, verify before removing:**
- `ScoringConfig.enabled` (`config.py:171`) — checked in `main.py:121, 146`
  and `__init__.py`. Round 8 directive: "all scoring-related data should
  always be computed", so this top-level toggle is obsolete. Remove the
  field and replace the call sites with the unconditional branch.
- Each per-dimension `enabled` flag (`cabin_density.enabled`,
  `accessibility.enabled`, `ar5_land_use.enabled`, `fishing.enabled`) —
  same reasoning. They gate work in `scoring/__init__.py:55,72,81,93` and
  `data_export.py:142,145,157,164`. Remove the fields and the gating;
  every dimension is always computed and always serialized.
- `InteractiveDimensionToggles` (`config.py:46–52`) — these toggles decide
  whether a card is rendered in the UI. Now that the cards exist for every
  dimension and users hide them via the per-card checkbox (round 7), the
  config-level toggle is redundant. Remove the class, the
  `dimension_toggles` field on `InteractiveControlsConfig`, the
  serialization in `data_export.py:171–177`, and the consumer in `app.js`
  (`Grep` for `dimension_toggles`).
- `InteractiveControlsConfig.enabled` (`config.py:103`) — same idea: the
  panel is always shown. Remove the field, the `if ctrl.enabled` branch in
  `data_export.py:169`, and the corresponding handling in `app.js`.
- `min_lake_area: bool` (`config.py:107`) — controls whether the filter
  slider is shown. The slider is always shown now; remove it.
- `*Slider.enabled` / `*Buffers.enabled` / `*Genera.enabled` (the four
  child models) — same reasoning. Each sub-control is always present.
  Either delete the `enabled` field on each model or, if the class becomes
  trivial after removal, delete the whole class and inline the remaining
  fields directly on `InteractiveControlsConfig`.

**For each removal:**
1. `Grep` the field name across `src/`, `web/`, and `config_*.yaml`.
2. Delete the producer (config field + any default-factory usage).
3. Delete the consumer (the `if cfg.x.enabled:` branch and the
   corresponding `app.js` code that read it).
4. Run `uv run telttur generate --config config.yaml` to confirm no
   crashes and the resulting `data.js` is byte-similar to before (only
   missing the dead fields).

**Update the YAML configs** (`config.yaml`, `config_norway.yaml`,
`config_akershus.yaml`, `config_akershus_test.yaml`, `config_innlandet.yaml`,
`config_mini.yaml`) — strip any of the removed keys so they don't fail
Pydantic validation. Pydantic's default is `extra="ignore"`, so unknown
fields won't error, but the YAML should still be cleaned up.

---

## 5. Clean up `web/app.js`

### 5a. Remove the debug-buildings layer

Round 8 directive: "remove debugging code from app.js". The
`_debugBldgLayer` block was only populated when `generate
--debug-buildings` was passed, which is not part of the normal flow.

**`web/app.js`:**
- Delete the `_debugBldgLayer` declaration (`app.js:115`).
- Delete the entire `if (data.debug_buildings) { … }` block
  (`app.js:495–532`).
- `Grep` for any `.tt-debug-btn` style in `web/style.css` and remove it.

**Do NOT remove the `--debug-buildings` CLI flag, `extract_buildings_all`,
or the `debug_buildings=...` argument to `export_data`** — the *Misc.*
section of `xx-misc-issues.md` explicitly says "Leave it for now". The
pipeline can still emit the field; the frontend simply ignores it. A
later task may turn this into a config option.

### 5b. Remove the "run telttur generate" error hint

Round 8 directive: "remove the 'run telttur generate' error message from
app.js". The hint is unhelpful for the actual users of the published site
— they cannot run `uv` anywhere — and it leaks developer terminology into
the user-facing UI.

**`web/app.js`:**
- Delete the `error_no_data_hint` key from `I18N` (`app.js:54`).
- Simplify the failure branch (`app.js:946–950`) to show only
  `error_no_data` (or replace with a single user-facing sentence like
  "Kartdata mangler. Prøv igjen senere."). Pick one — the file currently
  only renders `error_no_data` + `error_no_data_hint`, so the simplest
  change is to drop the `<p>` line entirely.

### 5c. Quick sweep for stale comments and dead helpers

While in `app.js`, look for:
- Comments referencing removed features (e.g. language switcher, legend
  positioning, AR5 WMS overlay). Round 7 already removed the language
  switcher; round 8 should catch any orphaned comments.
- Unused top-level `let` declarations after the debug-layer removal.
- The `// LayerGroup for debug building points (optional)` comment —
  gone with the variable.

Do *not* do a full refactor here. This is a deletion-only pass.

---

## 6. Verification checklist

After all steps:

- [ ] `uv run ruff check` clean.
- [ ] `uv run ty check` clean.
- [ ] `uv run telttur generate --config config.yaml` succeeds.
- [ ] `uv run telttur generate --config config_norway.yaml` succeeds and
      produces a `data.js` of comparable size to the pre-cleanup version
      (differences should be limited to removed config keys in the
      `config` block).
- [ ] Opening `output/data.js`-backed `web/index.html` in a browser shows
      the map exactly as before: same lakes, same scoring, same colours,
      same controls, same popups. Toggle each scoring card, move each
      slider, re-colour works.
- [ ] `uv run telttur --help` shows only the `generate` command.
- [ ] `uv run telttur generate --help` no longer lists `--profile` or
      `--skip-download`.
- [ ] `README.md` and `CLAUDE.md` no longer mention removed commands or
      flags.
