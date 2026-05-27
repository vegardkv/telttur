# Telttur – Claude Code Guide

## Project Overview

**Telttur** generates interactive camping/tenting suitability maps for Norway. A Python pipeline
processes geospatial data from Geonorge and outputs `data.js`, which a static Leaflet frontend
(`web/`) consumes. The map is published as a static site (no server required).

## Architecture

```
Python pipeline (uv run telttur generate)
    → output/data.js          (pre-computed lake scores, road geometries, scoring config)

web/index.html + web/app.js + web/style.css
    → reads output/data.js    (Leaflet + vanilla JS, no build step)
```

Key points:
- **No Folium** — the frontend migration (task 19) is complete. Do not add Folium code.
- The frontend works when opened via `file://` (no server). ES modules are therefore not an option.
- All geospatial processing is in Python (GeoPandas, Shapely, Fiona).
- Config is driven by Pydantic models in `src/telttur/config.py`.

## Common Commands

All Python/tool invocations go through `uv`. Never call `python`, `ruff`, `ty`, etc. directly.

```bash
# Primary workflow
uv run telttur generate --config my-config.yaml
uv run telttur generate --skip-download     # Reuse cached data

# Run the pipeline (will probably be deprecated)
uv run telttur generate --profile local     # Oslo area (quick)
uv run telttur generate --profile regional  # Akershus
uv run telttur generate --profile national  # All of Norway

# Other CLI commands (rarely used)
uv run telttur download
uv run telttur sample -o my-config.yaml --profile local
uv run telttur inspect data/n50/<path>.gdb

# Lint & format
uv run ruff check
uv run ruff format

# Type check
uv run ty check
```

## Project Structure

```
src/telttur/
├── main.py           # CLI entry point (Click)
├── config.py         # Pydantic config models
├── download.py       # Geonorge API download
├── roads.py          # Road extraction & buffering
├── lakes.py          # Lake extraction
├── landcover.py      # Land cover (WMS / vector)
├── data_export.py    # Outputs data.js for the frontend
└── scoring/          # Scoring dimensions: cabin, accessibility, ar5, fishing

web/
├── index.html
├── app.js            # All frontend logic (~900 lines, single file)
└── style.css
```

## Design Principles

- **Minimal interface** — expose only what's necessary.
- **DRY / KISS** — no over-engineering. Three similar lines beats a premature abstraction.
- `config.yaml` should stay lean — only the bare minimum of inputs, no redundant optional fields.

## Python Guidelines

- Pydantic models for all config; use `Field(default_factory=...)` for mutable defaults.
- Line length: 100. Target: Python 3.12.
- Ruff rules in effect: `E, F, I, UP, B, SIM, PTH, PLR0913, PLR2004`.
- Type annotations on all public functions; run `uv run ty check` before committing.

## JavaScript Guidelines

The `web/` frontend is a single-file vanilla JS app — no build step, no module system.

- **No inline event handlers** — use `addEventListener`, never `onclick`/`oninput` attributes.
- **No ES modules** — `file://` compatibility means no `type="module"`.
- **Single file is intentional** — at current scale (~900 lines) splitting adds CORS complexity.
- **Bitmasks** are acceptable for compact per-lake flags (e.g. fishing genera).
- **Prefer optional chaining** (`a?.b ?? default`) over verbose `&&` chains.
- **Modern browsers only** — use standard CSS (`appearance`, `::slider-thumb`) and modern JS
  (`?.`, `??`, `structuredClone`, etc.) freely. No vendor prefixes needed.
- noUiSlider (loaded via CDN) is the slider library. All sliders use it for visual consistency.

## Configuration Files

| File | Purpose |
|------|---------|
| `config.yaml` | Default local/dev config (minimal) |
| `config_akershus_test.yaml` | Regional scaling test (Akershus) |
| `config_innlandet.yaml` | Regional test (Innlandet) |

## Scoring Dimensions

| Dimension | Description |
|-----------|-------------|
| `cabin_density` | Building density around the lake shore (lower = better) |
| `accessibility` | Distance from road (configurable preferred range) |
| `ar5_land_use` | Proximity to residential/industrial AR5 zones |
| `fishing` | Lake contains prized fish species |

## Data Sources

All from [Geonorge](https://kartkatalog.geonorge.no/) (CC BY 4.0):
- **Roads/Lakes/Buildings**: N50 Kartdata (Kartverket)
- **Land cover overlay**: FKB-AR5 WMS (NIBIO/Kartverket)

## Tasks

Completed task specs live in `tasks/`. They document the feature history and design decisions —
useful context when changing existing behaviour.
