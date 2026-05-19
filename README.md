# Telttur

Generate interactive camping suitability maps for Norway. Shows road buffer zones, lake locations,
and land cover to help find ideal tent-by-the-lake spots within walking distance of your car.

## Features

- **Road buffer zones**: Visualize how far you're willing to walk from the car (configurable distance)
- **Lake overlay**: All lakes shown as colored polygons, classified by reachability from roads
- **Land cover**: See terrain type (forest, mountain, urban) via WMS overlay
- **Lake classification** (optional): Rate lakes by building/cabin density around the shore
- **Interactive HTML**: Pan/zoom, toggle layers, click lakes for details

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

### Quick start with a built-in profile

Three scale profiles are available — `local` (Oslo area), `regional` (Akershus), `national` (all of Norway):

```bash
# Generate directly from a profile
uv run telttur generate --profile local

# Or generate a full config file to customise, then run from it
uv run telttur sample -o my-config.yaml --profile local
uv run telttur generate --config my-config.yaml
```

The generated file contains every available option with its default value filled in, ready to edit.

### Custom configuration

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
1. Download N50 Kartdata from Geonorge for the relevant fylke(r)
2. Extract and buffer roads
3. Extract and classify lakes
4. Generate an interactive HTML map in `output/map.html`

### Other commands

```bash
# Skip download (reuse previously downloaded data)
uv run telttur generate --skip-download

# Download data only
uv run telttur download

# Inspect layers in a downloaded .gdb file
uv run telttur inspect data/n50/34_Innlandet/Basisdata_34_Innlandet_25833_N50Kartdata_FGDB.gdb
```

### Reducing output file size

Optimization (variable name shortening, coordinate precision reduction, CSS class extraction,
whitespace stripping) runs automatically after every `generate`. It is controlled by two fields
in `config.yaml`:

```yaml
output:
  minify: true          # enabled by default
  coordinate_precision: 6  # decimal places for lat/lng (~0.1 m accuracy)
```

To disable it (e.g. for debugging the raw Folium output):

```yaml
output:
  minify: false
```

To post-process an existing HTML file without re-running the full pipeline:

```bash
uv run telttur optimize --input output/map_norway.html
# overwrites in-place; use --output to write elsewhere:
uv run telttur optimize --input output/map_norway.html --output output/map_norway_opt.html
# adjust coordinate precision (default 6):
uv run telttur optimize --input output/map.html --precision 5
```

Typical reduction is around **40%** (e.g. 224 MB → 135 MB for a full-Norway map).

## Data Sources

All data from [Geonorge](https://kartkatalog.geonorge.no/) (CC BY 4.0):

| Layer | Dataset | Source |
|-------|---------|--------|
| Roads | N50 Kartdata — Samferdsel | Kartverket |
| Lakes | N50 Kartdata — Arealdekke | Kartverket |
| Buildings | N50 Kartdata — BygningerOgAnlegg | Kartverket |
| Land cover (WMS) | FKB-AR5 | NIBIO/Kartverket |

## Development

```bash
# Lint
uv run ruff check src/
uv run ruff format src/

# Type check
uv run ty check src/
```

## Project Structure

```
telttur/
├── config.yaml              # Area & parameter configuration
├── pyproject.toml
├── src/telttur/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Config loading
│   ├── download.py          # Geonorge API download
│   ├── roads.py             # Road extraction & buffering
│   ├── lakes.py             # Lake extraction & reachability
│   ├── landcover.py         # Land cover (WMS / vector)
│   ├── lake_classification.py  # Building density classification
│   └── map_generator.py     # Folium HTML map generation
├── data/                    # Downloaded geodata (gitignored)
└── output/                  # Generated maps (gitignored)
```
