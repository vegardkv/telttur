# Task 32 – Single-file HTML embed

## Goal

Add a pipeline option to embed `style.css` and `app.js` inline into a single self-contained HTML file. Update the GitHub Actions workflow to produce this embedded artifact.

## Background

Currently the web app consists of three separate files (`index.html`, `style.css`, `app.js`) plus the data file. For easy sharing and GitHub Pages deployment, it's useful to have a single `.html` file that bundles everything (CSS inlined in a `<style>` tag, JS inlined in `<script>` tags, data inlined as a `<script>` block).

The external CDN dependencies (Leaflet, noUiSlider) should remain as external `<script>`/`<link>` references — they are too large to inline and benefit from CDN caching.

## Design

### New CLI option or subcommand

Add a `--embed` flag (or a separate `embed` subcommand) to the `telttur` CLI that:

1. Reads `web/index.html`, `web/style.css`, `web/app.js`, and the generated `output/data.js`
2. Replaces the `<link rel="stylesheet" href="style.css">` with an inline `<style>…</style>` block
3. Replaces the `<script src="app.js"></script>` with an inline `<script>…</script>` block
4. Replaces the `<script src="../output/data.js"></script>` with an inline `<script>…</script>` block
5. Writes the result to the output directory (e.g. `output/map.html`)

### Implementation location

Add a function in `data_export.py` (or a new `embed.py` module) that performs the inlining. Wire it into the CLI.

### GitHub Actions update

Update `.github/workflows/generate-akershus.yml` to:
- Run the embed step after map generation
- Upload the single-file HTML as the artifact (instead of or in addition to the current artifact)

## Files to modify

- [src/telttur/data_export.py](../src/telttur/data_export.py) or new `embed.py` — embed logic
- [src/telttur/main.py](../src/telttur/main.py) — CLI wiring
- [.github/workflows/generate-akershus.yml](../.github/workflows/generate-akershus.yml) — updated build step

## Acceptance criteria

- Running the embed command produces a single `.html` file that works when opened directly in a browser
- External CDN references (Leaflet, noUiSlider) are preserved as-is
- The GitHub Actions workflow produces the embedded file as an artifact
- The original multi-file setup continues to work for development
