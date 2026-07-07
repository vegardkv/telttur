# Telttur

Generate interactive camping suitability maps for Norway. Lakes are scored on cabin density,
accessibility (distance and climb from the nearest road or public-transport stop), proximity to
built-up areas, and fishing potential — to help find ideal tent-by-the-lake spots.

A full model for Norway is available at https://turvann.no/

## How it works

```
Python pipeline (uv run telttur generate)
    → output/data.js          (pre-computed lake scores, road geometries, scoring config)

web/index.html + web/app.js + web/style.css
    → reads output/data.js    (Leaflet + vanilla JS, no build step, works via file://)
```

The pipeline downloads geodata, computes raw per-lake metrics (distances, densities, bitmasks),
and exports them to `output/data.js`. The static frontend converts metrics to scores in the
browser, so all scoring thresholds are adjustable live with sliders — no server required.

## Features

- **Lake scoring**: every lake rated on cabin density, accessibility, land-use proximity, and
  prized fish species
- **Interactive controls**: adjust scoring thresholds, filter by lake size, pick road vs
  public-transport access — all recomputed live in the browser
- **Road overlay**: N50 road centerlines colored by category
- **Restriction flags**: drinking-water source lakes (camping restrictions apply)
- **Single-file embed** (optional): bundle data + frontend into one self-contained HTML file

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

Edit or create a `config.yaml`. The minimum required field is either `bbox` or `fylke`:

```yaml
# Option A: explicit bounding box
bbox:
  north: 61.2
  south: 60.8
  east: 10.0
  west: 9.4

# Option B: named fylke (resolves to a preset bounding box)
fylke: Innlandet
```

Then generate:

```bash
uv run telttur generate
# or explicitly:
uv run telttur generate --config my-config.yaml
```

This will:
1. Download N50 Kartdata from Geonorge for the relevant fylke(r) (cached under `data/`)
2. Extract roads and lakes
3. Score all lakes (buildings, road/transit distance + elevation gain, AR5 land use, fish data)
4. Export `output/data.js`

View the map by opening `web/index.html` in a browser (it reads `output/data.js` directly).

## Data Sources

All from [Geonorge](https://kartkatalog.geonorge.no/) (CC BY 4.0) unless noted:

| Layer | Dataset | Source |
|-------|---------|--------|
| Roads / Lakes / Buildings | N50 Kartdata | Kartverket |
| Land use zones | FKB-AR5 WFS (N50 fallback) | NIBIO/Kartverket |
| Elevation | DTM50 via WCS | Kartverket |
| Public-transport stops | National aggregated GTFS (NLOD) | Entur |
| Fish observations | Vanninfo fisk | NINA |
| Drinking-water sources | Innsjø drikkevann WMS | Mattilsynet |

## Development

```bash
# Lint
uv run ruff check
uv run ruff format

# Type check
uv run ty check

# Tests
uv run pytest
```

See `CLAUDE.md` for architecture notes, design principles, and coding guidelines.

## Project Structure

```
telttur/
├── config.yaml              # Area & parameter configuration
├── pyproject.toml
├── src/telttur/
│   ├── main.py              # CLI entry point (Click)
│   ├── config.py            # Pydantic config models
│   ├── download.py          # Geonorge API download
│   ├── geo.py               # Shared CRS constants & helpers
│   ├── roads.py             # Road extraction & styling
│   ├── lakes.py             # Lake extraction
│   ├── elevation.py         # DTM50 download & sampling
│   ├── transport.py         # Entur GTFS stop extraction
│   ├── restrictions.py      # Drinking-water restriction flags
│   ├── data_export.py       # Outputs data.js for the frontend
│   ├── embed.py             # Optional single-file HTML embed
│   └── scoring/             # Scoring dimensions (cabin, access, AR5, fishing)
├── web/                     # Static frontend (Leaflet + vanilla JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/                    # Downloaded geodata (gitignored)
├── output/                  # Generated data.js (gitignored)
└── tasks/                   # Incremental development tasks
```
