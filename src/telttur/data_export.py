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


def build_config_block(config: Config) -> dict[str, Any]:
    """Extract scoring thresholds and interactive control defaults for the frontend."""
    scoring_cfg: dict[str, Any] = {}

    if config.scoring.cabin_density.enabled:
        t = config.scoring.cabin_density.thresholds
        scoring_cfg["cabin_density"] = {
            "enabled": True,
            "thresholds": {
                "excellent": t.excellent,
                "good": t.good,
                "fair": t.fair,
                "poor": t.poor,
            },
        }

    if config.scoring.accessibility.enabled:
        t2 = config.scoring.accessibility.thresholds
        scoring_cfg["accessibility"] = {
            "enabled": True,
            "thresholds": {
                "excellent": t2.excellent,
                "good": t2.good,
                "fair": t2.fair,
                "poor": t2.poor,
            },
        }

    if config.scoring.ar5_land_use.enabled:
        scoring_cfg["ar5_land_use"] = {
            "enabled": True,
            "residential_buffer_m": config.scoring.ar5_land_use.residential_buffer_m,
            "industrial_buffer_m": config.scoring.ar5_land_use.industrial_buffer_m,
        }

    if config.scoring.fishing.enabled:
        scoring_cfg["fishing"] = {"enabled": True, "genera": _FISHING_PRIZED_GENERA}

    interactive_cfg: dict[str, Any] = {}
    ctrl = config.map.interactive_controls
    if ctrl.enabled:
        interactive_cfg["enabled"] = True
        dt = ctrl.dimension_toggles
        interactive_cfg["dimension_toggles"] = {
            "cabin_density": dt.cabin_density,
            "accessibility": dt.accessibility,
            "ar5_land_use": dt.ar5_land_use,
            "fishing": dt.fishing,
        }
        interactive_cfg["min_lake_area"] = ctrl.min_lake_area
        ar = ctrl.accessibility_range
        interactive_cfg["accessibility_range"] = {
            "enabled": ar.enabled,
            "min_m": ar.min_m,
            "max_m": ar.max_m,
            "slider_max_m": ar.slider_max_m,
        }
        cd = ctrl.cabin_density_slider
        interactive_cfg["cabin_density_slider"] = {
            "enabled": cd.enabled,
            "value": cd.value,
            "slider_max": cd.slider_max,
        }
        ar5b = ctrl.ar5_buffers
        interactive_cfg["ar5_buffers"] = {
            "enabled": ar5b.enabled,
            "slider_max_m": ar5b.slider_max_m,
        }
        fg = ctrl.fishing_genera
        interactive_cfg["fishing_genera"] = {"enabled": fg.enabled}
    else:
        interactive_cfg["enabled"] = False

    return {
        "scoring": scoring_cfg,
        "interactive": interactive_cfg,
        "min_lake_area_m2": config.min_lake_area_m2,
        "level_names": LEVEL_NAMES,
        "level_colors": LEVEL_COLORS,
    }


def export_data(
    lakes: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    config: Config,
    output_path: Path,
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
    config_block = build_config_block(config)

    data = {
        "meta": meta,
        "lake_fields": lake_fields,
        "lakes": lake_rows,
        "roads": road_data,
        "config": config_block,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    js_path = output_path.with_suffix(".js")
    with js_path.open("w", encoding="utf-8") as f:
        f.write(f"window.TELTTUR_DATA={json_str};")
