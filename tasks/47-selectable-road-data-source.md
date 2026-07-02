# Task 47 – Selectable road data source for accessibility

## Objective

Make the **drivable-road network used by accessibility scoring** a selectable, config-driven
choice, with the **current N50 approach as one of the options**. Today accessibility snaps
each lake to the nearest road from N50, filtered by `excluded_road_types`
(`scoring/accessibility.py:109-114`, default excludes `["P", "sti", "gangOgSykkelveg",
"traktorveg"]`). That filter is crude: N50's `vegkategori` is an **ownership** classification,
not a drivability one — so excluding all `P` (privat veg) wrongly drops toll/bom roads and
other private-but-public-drivable roads, while including all `P` would let in driveways and
genuinely closed roads.

The goal is **not** to pick the perfect source up front, but to make the source pluggable so
the options can be **run side-by-side and compared** on real cases. One of them may be
removed later once a winner is clear.

## Context — the case that motivated this

A road near Blefjell (Telemark) that is genuinely drivable (a small-fee *bomveg*) is classed
`P` in N50 and therefore excluded, so a nearby lake snaps to a farther road and scores worse
than it should. Investigated with the debug map from the previous session
(`src/telttur/debug_map.py`, `debug_map: true`) — the road's popup confirmed `category = P`,
EXCLUDED.

Key finding: **N50 carries no public-access attribute.** It only guarantees roads are
*physically* drivable and >50 m long; whether the public may legally drive is not encoded.
References:
- SOSI Vegkategori code list — https://register.geonorge.no/sosi-kodelister/kartdata/vegkategori
- N50 Kartdata product spec — https://register.geonorge.no/register/versjoner/produktspesifikasjoner/kartverket/n50-kartdata
- NVDB Datakatalog (Statens vegvesen) — https://www.vegvesen.no/fag/teknologi/nasjonal-vegdatabank/datakatalogen/
- NVDB Datakatalog (searchable) — https://labs.vegdata.no/nvdb-datakatalog/

## The options to support

A road source produces the **drivable road `LineString` network** (in `CRS_UTM33`) that
feeds the existing nearest-road scoring. All three must plug into the *same* downstream
scoring path so results are directly comparable.

| Option | Source | Drivability signal | Trade-off |
|--------|--------|--------------------|-----------|
| **`n50`** (current, default) | N50 `vegkategori`/`typeveg`, already extracted in `roads.py` | `excluded_road_types` filter | No public-access info; over- or under-filters `P`. Zero new data. |
| **`nvdb`** | NVDB / **Elveg 2.0** (via Geonorge) | Toll stations (*bom*), *motorferdselsforbud*, traffic regulations, public-vs-private — the authoritative attributes N50 lacks | Most accurate; new data source + heavier model to parse. |
| **`osm`** | OpenStreetMap | `access` / `motor_vehicle` / `access=private\|permissive\|destination`, `barrier=gate`, `toll=yes` — de-facto public-drivability tags | Pragmatic, good coverage; tag completeness varies; new ingestion + licensing (ODbL). |

## Research first (do not trust the table above blindly)

This mirrors task 45's "the hard part is the data" framing. Before wiring anything:

1. **NVDB / Elveg 2.0**: confirm which Geonorge dataset/distribution carries the needed
   attributes (toll/bom, motorferdsel, public/private), how it's keyed to road links, and
   whether a Norway-wide bulk download is feasible (mirror the N50 download/caching pattern,
   not per-query NVDB API calls — same reasoning as Entur GraphQL in task 45). Define the
   exact rule for "publicly drivable" from its attributes.
2. **OSM**: decide the extract source (e.g. Geofabrik Norway PBF) and the tag rule that means
   "public may drive" (e.g. `highway` in a driveable set AND `motor_vehicle`/`access` not in
   `{no, private}`; `toll=yes` is a positive signal). Decide ingestion (osmium/pyrosm/overpass
   bulk) without adding a heavy dependency if avoidable (CLAUDE.md: lightweight deps).
3. **Hand-validate each source on the Blefjell bomveg** and 2-3 other known cases (one that
   *should* be drivable, one driveway that should *not*) so the comparison has ground truth.

## Suggested design

### Config (`src/telttur/config.py`)
- Add a `RoadSource` StrEnum mirroring `Ar5DataSource` (lines 124-129): `N50 = "n50"`,
  `NVDB = "nvdb"`, `OSM = "osm"`.
- Add `road_source: RoadSource = RoadSource.N50` to `AccessibilityConfig` (lines 115-122).
  Keep `excluded_road_types` — it stays the knob for the `n50` source. Keep `config.yaml`
  lean (CLAUDE.md): per-source URLs/filenames are module constants, not config.

### Drivable-network abstraction
- A single function that returns the drivable network for the chosen source, e.g.
  `get_drivable_roads(source, *, n50_roads, bbox, cache_dir, excluded_road_types) ->
  gpd.GeoDataFrame` (LineStrings in `CRS_UTM33`). Dispatch on `source`:
  - `n50` → the **current** behaviour, factored out of `accessibility.py:109-114`
    (filter `n50_roads` by `excluded_road_types`). No regression for the default.
  - `nvdb` → new module `src/telttur/roadsrc_nvdb.py`: download/cache Elveg 2.0, filter to
    publicly drivable links per the researched rule.
  - `osm` → new module `src/telttur/roadsrc_osm.py`: load OSM extract, filter by access tags.
- Mirror existing source modules for download+cache shape (`transport.py` `ensure_gtfs`,
  `elevation.py` `ensure_dem`, `fishing.py` archive caching).

### Scoring wiring (`src/telttur/scoring/accessibility.py`, `scoring/__init__.py`)
- `score_accessibility` already takes `road_lines` + `excluded_road_types`
  (`scoring/__init__.py:77-84`). Change it to obtain the drivable set via
  `get_drivable_roads(config.accessibility.road_source, ...)` instead of the inline
  `excluded`-filter, then feed the **same** `_score_origin`/`sjoin_nearest` path
  (`accessibility.py:30-80`). Distance + climb computation is unchanged — only *which lines
  count as drivable* changes, which is exactly what makes the options comparable.

### Comparison support
- The debug map (`src/telttur/debug_map.py`) is the natural comparison tool. Optionally let
  it render the drivable network of the selected `road_source` (or overlay each), so a run
  per source over the same bbox shows visually which roads each source treats as drivable.
- Because only the drivable-network step changes, running the pipeline with each
  `road_source` over the same config/bbox yields directly comparable `road_distance_m` /
  accessibility scores per lake.

## Notes / constraints
- **Fail fast** (CLAUDE.md / task 46): each non-N50 source must **raise and abort** if it
  can't download/parse — never silently fall back to an empty network or to N50. (A genuinely
  empty result within a valid bbox is fine, as for buildings.)
- **N50 stays the default** so existing behaviour and all current configs are unchanged.
- **Display vs scoring**: N50 remains the road *display* source (`show_roads`, debug map);
  this task changes only the *drivable network used for accessibility scoring*. Keep that
  separation explicit.
- **Licensing/attribution** (task 29 credits block in `app.js`, CLAUDE.md Data Sources table):
  NVDB/Elveg (NLOD) and OSM (ODbL) require attribution — add when their option is used.
- **Lightweight deps** (CLAUDE.md): prefer GeoPandas/Fiona/Shapely-based ingestion; justify
  any new dependency (e.g. an OSM PBF reader) before adding it.
- **Don't over-build**: v1 is source *selection* + a defensible drivability rule per source.
  Fancier modelling (per-link confidence, blending sources) is out of scope.

## Acceptance criteria
- [ ] `AccessibilityConfig.road_source` selects the drivable-road source (`n50` | `nvdb` |
      `osm`); default `n50` reproduces today's results exactly (the current
      `excluded_road_types` filter is the `n50` path).
- [ ] Each non-N50 source is researched, its "publicly drivable" rule documented, and
      hand-validated on the Blefjell bomveg + a few known drivable/closed cases.
- [ ] Non-N50 sources download once and cache (mirroring N50/DTM/GTFS), and **fail hard** on
      fetch/parse errors — never silently empty.
- [ ] All sources feed the same `_score_origin` scoring path, so switching `road_source` is
      the only variable when comparing results over a fixed bbox.
- [ ] The Blefjell bomveg is treated as drivable under at least one new source, and that
      lake's `road_distance_m` improves accordingly.
- [ ] NVDB/Elveg and OSM are attributed (credits block + CLAUDE.md Data Sources) when used.
- [ ] `uv run ruff check`, `uv run ruff format`, `uv run ty check` all pass.
