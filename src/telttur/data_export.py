"""Export pipeline data to JSON for the static Leaflet frontend."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from telttur.config import Config
from telttur.lakes import LakeCols
from telttur.scoring import (
    LEVEL_COLORS,
    LEVEL_NAMES,
)
from telttur.scoring.fishing import PRIZED_GENERA as _FISHING_PRIZED_GENERA

# Coordinate precision: 6 decimals ≈ 0.1 m accuracy, sufficient for maps.
_COORD_PRECISION = 6


def build_lake_data(
    lakes: gpd.GeoDataFrame,
) -> tuple[list[list[Any]], list[str]]:
    """Convert the lakes GeoDataFrame to a compact array-of-arrays.

    Returns (rows, field_names).  Each row is a list whose position corresponds
    to the matching entry in field_names.  Only fields that are actually present
    in the GeoDataFrame are included.
    """
    # Determine which optional fields are present
    optional_cols = [
        LakeCols.FISH_GENERA_MASK,
        LakeCols.ROAD_DISTANCE_M,
        LakeCols.BUILDING_DENSITY,
        LakeCols.INDUSTRIAL_DISTANCE_M,
        LakeCols.RESIDENTIAL_DISTANCE_M,
        LakeCols.FISH_SPECIES_COUNT,
    ]
    present_optional = [c for c in optional_cols if c in lakes.columns]

    # Detect name column
    name_col: str | None = None
    for candidate in ("navn", "NAVN"):
        if candidate in lakes.columns:
            name_col = candidate
            break

    # Build field list: always lat/lng/area, then optional scoring cols, then name
    fields = ["lat", "lng", "area"] + present_optional
    if name_col is not None:
        fields.append("name")

    rows: list[list[Any]] = []
    for _, row in lakes.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        rep = geom.representative_point()
        lat = round(rep.y, _COORD_PRECISION)
        lng = round(rep.x, _COORD_PRECISION)
        area = float(row.get(LakeCols.AREA_M2, 0) or 0)

        entry: list[Any] = [lat, lng, round(area, 1)]
        for col in present_optional:
            val = row.get(col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                entry.append(None)
            elif col in (
                LakeCols.FISH_GENERA_MASK,
                LakeCols.FISH_SPECIES_COUNT,
            ):
                entry.append(int(val))
            else:
                entry.append(round(float(val), 1))

        if name_col is not None:
            name_val = row.get(name_col)
            entry.append(str(name_val) if name_val is not None else None)

        rows.append(entry)

    return rows, fields


def build_road_data(roads: gpd.GeoDataFrame) -> dict[str, Any]:
    """Convert roads GeoDataFrame to a GeoJSON FeatureCollection dict."""
    if roads.empty:
        return {"type": "FeatureCollection", "features": []}
    roads_wgs84 = roads.to_crs("EPSG:4326")
    # Round coordinates to reduce JSON size
    import shapely

    def _round_geom(geom: Any) -> Any:
        return shapely.set_precision(geom, 1e-6)

    roads_wgs84 = roads_wgs84.copy()
    roads_wgs84["geometry"] = roads_wgs84["geometry"].apply(_round_geom)

    # Keep only the columns needed for rendering
    keep = ["geometry"]
    for col in ("color", "label", "category"):
        if col in roads_wgs84.columns:
            keep.append(col)
    roads_wgs84 = roads_wgs84[keep]

    return json.loads(roads_wgs84.to_json())


def _compute_density_quantiles(lakes: gpd.GeoDataFrame, steps: int) -> list[float]:
    """Compute quantile boundaries for the building_density slider.

    Step 1 is always 0.0 (pristine lakes with no buildings nearby).
    Steps 2..N are evenly-spaced quantiles of the non-zero density values,
    so the slider range is informative rather than dominated by the zero mass.
    Falls back to a linear range ending at 0.15 when data is absent.
    """
    col = LakeCols.BUILDING_DENSITY
    fallback = [round(0.15 / steps * (i + 1), 4) for i in range(steps)]

    if col not in lakes.columns:
        return fallback

    nonzero = lakes[col].dropna()
    nonzero = nonzero[nonzero > 0]
    if nonzero.empty:
        return fallback

    remaining = steps - 1
    percentiles = [(i + 1) / remaining for i in range(remaining)]
    qs = nonzero.quantile(percentiles)
    return [0.0] + [round(float(v), 4) for v in qs]


def build_config_block(config: Config, lakes: gpd.GeoDataFrame) -> dict[str, Any]:
    """Extract scoring thresholds and interactive control defaults for the frontend."""
    t2 = config.scoring.accessibility.thresholds
    scoring_cfg: dict[str, Any] = {
        "accessibility": {
            "thresholds": {
                "excellent": t2.excellent,
                "good": t2.good,
                "fair": t2.fair,
                "poor": t2.poor,
            },
        },
        "ar5_land_use": {
            "residential_buffer_m": config.scoring.ar5_land_use.residential_buffer_m,
            "industrial_buffer_m": config.scoring.ar5_land_use.industrial_buffer_m,
        },
        "fishing": {"genera": _FISHING_PRIZED_GENERA},
    }

    ctrl = config.map.interactive_controls
    ar = ctrl.accessibility_range
    cd = ctrl.cabin_density_slider
    quantiles = _compute_density_quantiles(lakes, cd.steps)
    print("Cabin density quantiles for slider steps:", quantiles)
    ar5b = ctrl.ar5_buffers
    interactive_cfg: dict[str, Any] = {
        "accessibility_range": {
            "min_m": ar.min_m,
            "max_m": ar.max_m,
            "slider_max_m": ar.slider_max_m,
        },
        "cabin_density_slider": {
            "steps": cd.steps,
            "default_step": cd.default_step,
            "quantiles": quantiles,
        },
        "ar5_buffers": {
            "slider_max_m": ar5b.slider_max_m,
        },
    }

    return {
        "scoring": scoring_cfg,
        "interactive": interactive_cfg,
        "min_lake_area_m2": config.min_lake_area_m2,
        "level_names": LEVEL_NAMES,
        "level_colors": LEVEL_COLORS,
    }


def build_debug_buildings(buildings: gpd.GeoDataFrame) -> dict[str, Any]:
    """Convert debug building points to a compact JSON structure.

    Returns a dict with:
      ``fields``  — ["lat", "lng", "type"]
      ``rows``    — [[lat, lng, type_code], ...]

    Points where ``bygningstype`` is absent are exported with type_code ``null``.
    """
    bldgs_wgs84 = buildings.to_crs("EPSG:4326")
    rows: list[list[Any]] = []
    for _, row in bldgs_wgs84.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        lat = round(float(geom.y), _COORD_PRECISION)
        lng = round(float(geom.x), _COORD_PRECISION)
        type_code = row.get("bygningstype")
        is_missing = type_code is None or (isinstance(type_code, float) and pd.isna(type_code))
        type_val: int | None = None if is_missing else int(type_code)
        rows.append([lat, lng, type_val])
    return {"fields": ["lat", "lng", "type"], "rows": rows}


def export_data(
    lakes: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    config: Config,
    output_path: Path,
    *,
    debug_buildings: gpd.GeoDataFrame | None = None,
) -> None:
    """Assemble and write data.json for the static Leaflet frontend."""
    bbox = config.bbox
    assert bbox is not None  # guaranteed by Config.require_bbox validator
    meta: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "bbox": [bbox.south, bbox.west, bbox.north, bbox.east],
        "region": getattr(config, "fylke", None) or "custom",
    }

    lake_rows, lake_fields = build_lake_data(lakes)
    road_data = (
        build_road_data(roads)
        if config.show_roads
        else {"type": "FeatureCollection", "features": []}
    )
    config_block = build_config_block(config, lakes)

    data: dict[str, Any] = {
        "meta": meta,
        "lake_fields": lake_fields,
        "lakes": lake_rows,
        "roads": road_data,
        "config": config_block,
    }
    if debug_buildings is not None and not debug_buildings.empty:
        data["debug_buildings"] = build_debug_buildings(debug_buildings)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    js_path = output_path.with_suffix(".js")
    with js_path.open("w", encoding="utf-8") as f:
        f.write(f"window.TELTTUR_DATA={json_str};")
