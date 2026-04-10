# Task 5: Land Cover WMS Integration

## Objective
Verify that the FKB-AR5 WMS overlay works in the generated HTML map.

## Context
The AR5 land cover is displayed as a WMS tile overlay from NIBIO. The WMS URL used is `https://wms.nibio.no/cgi-bin/ar5` with layer `Arealtype`. This must be verified to work in the browser.

## Steps

1. **Generate a map with WMS mode** (default):
   ```bash
   uv run telttur generate --skip-download
   ```

2. **Open `output/map.html`** and check:
   - Toggle the "Arealressurskart (AR5)" layer ON
   - Verify that colored land cover tiles load
   - Check that the WMS tiles align with the base map (no offset)
   - Verify transparency works (you can see the base map through it)

3. **If the WMS URL doesn't work**, try alternatives:
   - Check the Geonorge metadata for the correct WMS endpoint
   - Try `https://wms3.nibio.no/cgi-bin/ar5` as alternative
   - Try adding `EPSG:3857` or `EPSG:4326` as the SRS parameter
   - Check browser console for CORS or 404 errors

4. **If WMS fails permanently**, implement a fallback:
   - Add a Kartverket topographic WMS as an alternative land cover visual
   - URL: `https://openwms.statkart.no/skwms1/wms.topo4` or similar

5. **Test the vector mode** as well:
   ```yaml
   landcover_mode: vector
   ```
   - Verify polygons are extracted and color-coded correctly

## Acceptance Criteria
- [ ] WMS land cover overlay loads in the browser
- [ ] Colors are clear and distinguish different land types
- [ ] Overlay aligns with the base map
- [ ] Alternative vector mode also works (if data is available in FGDB)
