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

### 1. Configure

Edit `config.yaml` to set your area of interest (bounding box) and buffer distance:

```yaml
bbox:
  north: 61.2
  south: 60.8
  east: 10.0
  west: 9.4
buffer_distance_m: 2000
```

### 2. Generate map

```bash
uv run telttur generate
```

This will:
1. Download N50 Kartdata from Geonorge for the relevant fylke(r)
2. Extract and buffer roads
3. Extract and classify lakes
4. Generate an interactive HTML map in `output/map.html`

### Options

```bash
# Use a different config file
uv run telttur generate --config my-config.yaml

# Skip download (reuse previously downloaded data)
uv run telttur generate --skip-download

# Download data only
uv run telttur download

# Inspect layers in a downloaded .gdb file
uv run telttur inspect data/n50/34_Innlandet/Basisdata_34_Innlandet_25833_N50Kartdata_FGDB.gdb
```

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
