# Task 29 – Attributions & data source licensing

## Goal

Add proper attributions to the web app and verify that all data source licenses permit publishing this map as a public website.

## Scope

### 1. Attribution section in the UI

Add an attribution/credits area to the map (e.g. in the legend panel, a footer bar, or a collapsible "About" section) that credits:

- **Kartverket** — N50 map data (roads, buildings, lakes) and base map tiles (already partially attributed via Leaflet tile layer attribution)
- **Kartverket / NIBIO** — AR5 land use data
- **Artsdatabanken / Lakseregisteret** — fish species data (if applicable)
- **Leaflet** — map library
- **GitHub link** — link to the project repository (`https://github.com/vegardkv/telttur`)

Note that task 27 added a data source section to the "info" hover for each scoring dimension. If this is sufficient wrt to attribution, no need to have this in the map attribution footer.

### 2. License & terms verification

Research and document (in this task file or a `LICENSES.md`) whether each data source permits:
- Public display on a website
- Derivative works (the scoring/processing we do)
- Commercial use (even if the site is non-commercial, good to know)

Data sources to check:
- **N50 Kartdata** (Kartverket) — check the `Mer_informasjon_om_N50Kartdata.txt` files in the data directory
- **AR5 land use** (NIBIO/Kartverket WMS) — check WMS service terms
- **Fish species data** — check Artsdatabanken/Lakseregisteret terms
- **Kartverket base map tiles** (topograatone/topo WMTS) — check tile service terms

### 3. I18N

Add translation keys for attribution text in both English and Norwegian.

## Files to modify

- [web/app.js](../web/app.js) — attribution UI, I18N keys
- [web/style.css](../web/style.css) — attribution styling
- Possibly a new `LICENSES.md` or update to `README.md`

## Acceptance criteria

- All data sources are properly credited in the map UI
- A link to the GitHub repository is visible
- License compatibility has been verified and documented
- Attributions are available in both languages
