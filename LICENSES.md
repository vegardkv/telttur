# Data Source Licenses

This document verifies the licensing terms for all external data sources used by Telttur.

## N50 Kartdata (Kartverket)

- **Data**: Roads, lakes, buildings, terrain
- **Provider**: Kartverket (Norwegian Mapping Authority)
- **License**: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- **Terms**: <https://www.kartverket.no/api-og-data/vilkar-for-bruk>
- **Catalogue**: <https://kartkatalog.geonorge.no/metadata/n50-kartdata/ea192681-d039-42ec-b1bc-f3ce04c189ac>
- **Public display**: ✅ Permitted
- **Derivative works**: ✅ Permitted
- **Commercial use**: ✅ Permitted
- **Attribution required**: "© Kartverket" with link to kartverket.no

## Kartverket Base Map Tiles (WMTS)

- **Data**: Topographic greyscale ("topograatone") and colour ("topo") map tiles
- **Provider**: Kartverket
- **License**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Terms**: <https://www.kartverket.no/api-og-data/vilkar-for-bruk>
- **Public display**: ✅ Permitted
- **Derivative works**: ✅ Permitted
- **Commercial use**: ✅ Permitted
- **Attribution required**: "© Kartverket" with link to kartverket.no
- **Note**: WMS/cache services at zoom levels 12–20 include Geovekst data. Kartverket states these can be used "as they are in various services" under the same terms.

## AR5 Land Use (NIBIO / Kartverket)

- **Data**: Arealressurskart AR5 — land use classification (residential, industrial zones)
- **Provider**: NIBIO (Norwegian Institute of Bioeconomy Research) / Geovekst
- **Access method**: NIBIO AR5 WFS at `wms.nibio.no/cgi-bin/ar5` (public endpoint)
- **Underlying dataset license**: [Norge digitalt-lisens](https://www.kartverket.no/geodataarbeid/norge-digitalt/partsinformasjon/avtaler-og-vilkar/norge-digitalt-lisens) (download restricted to Norge Digitalt partners)
- **WFS/WMS service usage**: The WFS is publicly accessible. Telttur fetches polygons during pipeline processing and stores only derived scalar values (distances to residential/industrial zones), not raw AR5 geometries. The published map contains no AR5 geometry data.
- **Public display**: ✅ Derived scores only (no raw data republished)
- **Derivative works**: ✅ (scalar distance values are derived, not copies)
- **Commercial use**: ⚠️ Underlying FKB-AR5 data is restricted; consult Norge digitalt terms for commercial redistribution of raw data
- **Attribution required**: Credit NIBIO and Kartverket

## NINA Vanndata fisk (Fish Observations)

- **Data**: Freshwater fish species occurrence records (~85,000 observations)
- **Provider**: Norsk institutt for naturforskning (NINA)
- **License**: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- **URL**: <https://ipt.nina.no/resource?r=vanninfofisk>
- **GBIF**: <https://www.gbif.org/dataset/a639542a-654a-427b-9cf1-bde1953bbb52>
- **Public display**: ✅ Permitted
- **Derivative works**: ✅ Permitted
- **Commercial use**: ✅ Permitted
- **Attribution required**: Credit NINA

## Leaflet (Map Library)

- **License**: [BSD 2-Clause](https://github.com/Leaflet/Leaflet/blob/main/LICENSE)
- **Attribution**: Leaflet includes its own attribution link by default

## Summary

| Data Source | License | Public Display | Derivatives | Commercial |
|---|---|---|---|---|
| N50 Kartdata (Kartverket) | CC BY 4.0 | ✅ | ✅ | ✅ |
| Kartverket WMTS tiles | CC BY 4.0 | ✅ | ✅ | ✅ |
| AR5 (NIBIO WFS) | Norge digitalt (public WFS) | ✅ (derived) | ✅ (derived) | ⚠️ |
| NINA Vanndata fisk | CC BY 4.0 | ✅ | ✅ | ✅ |
| Leaflet | BSD 2-Clause | ✅ | ✅ | ✅ |

All data sources permit publishing this map as a public website with proper attribution.
