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

## Data research findings (June 2026)

Researched all four candidate sources. **Bottom line:** the only authoritative
"this lake is a drinking-water source" dataset (Mattilsynet's) is published
**WMS-only** — there is no open WFS/vector download. So the join has to go through
the WMS, not a clean vector file like the NINA fishing archive. Recommendation and
the rejected alternatives are below.

### Candidates evaluated

| Source | What it is | Access | Verdict |
|--------|-----------|--------|---------|
| **Mattilsynet – Innsjø drikkevannforekomster** | Lakes that are WFD water bodies used for drinking-water production. Polygons, national. | **WMS only** (`kart.mattilsynet.no`). No WFS / no GeoJSON / no download API. Data frozen ~2018. Open (no use restrictions). | ✅ **Use this** — it is the authoritative drinking-water-lake layer. Join via WMS (see below). |
| **Vann-Nett "Beskyttede områder" (WFD Annex IV)** | Protected areas under the water regulations. Polygons, EPSG:25833, GeoJSON export, NLOD. | ArcGIS REST FeatureServer (queryable, exportable): `kart2.miljodirektoratet.no/arcgis/rest/services/vann_nett/ProtectedArea/FeatureServer/0` | ❌ **Rejected.** Confirmed the only `ProtectedAreaType` values are *Avløpsdirektivet, Nitratdirektivet, Badevann, Annet*. **No drinking-water category** — Norway's WFD drinking-water protected-area register is effectively not populated here. |
| **Miljødirektoratet "Vannforekomster"** | All WFD water bodies (lakes as polygons) with `vannforekomstID`. GeoJSON/GML/FGDB download, NLOD, national. Atom: `nedlasting.miljodirektoratet.no/miljodata/ATOM/Datasett/Vannforekomster.xml` | Open vector download. | ❌ **Rejected as the source** — carries ecological/chemical status but **no drinking-water flag**. (Could be a join key carrier, but Mattilsynet's layer isn't keyed for us to join to it — see below.) |
| **NVE Innsjødatabase** | ~243 000 lakes >2500 m² with `vatn_lnr`. WFS available. | Geonorge WFS. | ❌ **Rejected.** Attributes are watershed nr / reservoir nr / name / kommune — **no drinking-water attribute**. |
| **Mattilsynet "Drikkevann – inntakspunkter"** (intake points) | Point locations where utilities abstract water. Would enable a clean point-in-lake join (like fishing). | Geonorge DOK status = **"Ikke levert"** for WMS/WFS/Atom/download. Only the WMS layer `Mattilsynet_Vannverk_Inntakspunkter` exists. | ⚠️ Fallback only — same WMS-only constraint, no vector download. |

### Recommended source + join

**Source:** Mattilsynet WMS, layer **`Mattilsynet_Innsjo_Drikkevann`**
(there is also a dated snapshot `Mattilsynet_Innsjoer_Drikkevann_201804010`; prefer the
undated name). Endpoint:

```
https://kart.mattilsynet.no/wmscache/service?
```

Confirmed: open (no auth), `queryable="1"` (supports **GetFeatureInfo**), supports
**EPSG:25833** (same CRS the pipeline already works in), WMS 1.3.0.
GetFeatureInfo `info_format`: `text/plain`, `text/html`, `text/xml` (no JSON — parse XML/plain).

Because there is no vector layer, the join must sample the WMS. Two viable patterns;
**Option A is recommended** for v1:

- **Option A — GetFeatureInfo per lake (point-in-polygon).** For each candidate lake,
  issue one WMS GetFeatureInfo at the lake's representative point (use
  `geometry.representative_point()`, not centroid — centroids of crescent lakes can fall
  outside the polygon). A non-empty feature response → set the drinking-water bit.
  - Simple, exact, returns structured attributes. No image parsing.
  - Cost = one HTTP request per lake. Fine at regional scale (Akershus/Innlandet runs are
    a few thousand lakes after the min-area filter); cache responses keyed by lake id so
    re-runs are free. For a national run this is the slow path — see Option B.
  - Build the GetFeatureInfo URL with a tiny 1×1 or small BBOX around the point in
    EPSG:25833; request `info_format=text/xml`; treat any returned feature as a hit.

- **Option B — GetMap raster mask (scales to national).** Tile the bbox, GetMap the
  drinking-water layer as PNG (transparent background), build a boolean "painted" mask,
  then flag any lake polygon overlapping a painted cell. One request per tile, fully
  offline join afterward — mirrors how elevation is fetched as a raster (DTM via WCS →
  GeoTIFF, see accessibility/elevation path). More code (rasterio, alpha threshold, tile
  bookkeeping) and slightly fuzzy at lake edges; only worth it if national runs matter.

**Before wiring through:** the chosen Mattilsynet layer is a **~2018 snapshot** and may
be incomplete for small utilities. Worth a 5-minute manual check of
`kart.mattilsynet.no/geoserver` (returns 401 — needs the right workspace/credentials) or
a mail to the dataset contact (Olav Vatn, olav.vatn@mattilsynet.no) in case a direct
vector file (SOSI/FGDB) can be obtained — that would replace the WMS scrape with a clean
vector spatial join and is strictly better if available.

### Hand-validation lakes (do this first)

Pick known municipal drinking-water sources and confirm the layer flags them:
- **Maridalsvannet** (Oslo's primary drinking-water source) ≈ 59.98 N, 10.78 E — ideal,
  inside the default Oslo/Akershus bbox.
- **Jonsvatnet** (Trondheim) ≈ 63.39 N, 10.56 E.
- **Farrisvannet / Farris** (Larvik) ≈ 59.10 N, 10.00 E.
- Negative control: a nearby non-source lake of similar size should **not** flag.

### Implications for the design below

- This is **not** a vector file you load once (unlike the NINA fishing archive), so the
  "new module downloads + loads the dataset" step becomes "module queries the Mattilsynet
  WMS per lake (Option A) and caches results". Keep the per-lake HTTP behind a cache file
  in `data_dir` so generation is repeatable offline (consistent with the N50/NINA caches).
- No config knob needed: the WMS URL + layer name are constants (like `AR5_WMS_URL` in
  `landcover.py`). Keeps `config.yaml` lean as required.
- Credits/licensing: attribute **Mattilsynet** (open data, "ingen begrensninger på bruk").
  Source: Geonorge metadata `50f62bbe-b216-4e38-bd75-1a54744c1a53`.

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
