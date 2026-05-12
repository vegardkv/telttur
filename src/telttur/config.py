from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class BBox(BaseModel):
    north: float
    south: float
    east: float
    west: float


class CabinDensityThresholds(BaseModel):
    """Density thresholds for cabin density scoring (upper bound per level).

    The density metric is ``building_count / sqrt(area_m2)``, which normalises
    for lake size so that a large remote lake with a handful of cabins does not
    score the same as a small urban pond with the same number of buildings.

    A lake receives a level if its building_density is <= the threshold for that
    level.  Lakes exceeding the 'poor' threshold are scored Terrible.
    """

    excellent: float = 0.0    # pristine: no buildings at all
    good: float = 0.01        # e.g. ≤3 buildings around a 90 000 m² lake
    fair: float = 0.05        # e.g. ≤5 buildings around a 10 000 m² lake
    poor: float = 0.15        # above this → Terrible


class AccessibilityThresholds(BaseModel):
    """Distance thresholds (metres) for accessibility scoring (upper bound per level).

    A lake receives a level if its road_distance_m is <= the threshold for that level.
    Lakes farther than the 'poor' threshold are scored Terrible.
    """

    excellent: float = 500.0    # < 500 m  → Excellent
    good: float = 1000.0        # < 1 km   → Good
    fair: float = 2000.0        # < 2 km   → Fair
    poor: float = 5000.0        # < 5 km   → Poor; ≥ 5 km → Terrible


class MapConfig(BaseModel):
    """Configuration for map rendering options."""

    include_osm_layer: bool = False


class CabinDensityConfig(BaseModel):
    """Configuration for cabin density scoring dimension."""

    enabled: bool = True
    buffer_m: float = 200.0
    thresholds: CabinDensityThresholds = Field(default_factory=CabinDensityThresholds)


class AccessibilityConfig(BaseModel):
    """Configuration for accessibility scoring dimension."""

    enabled: bool = True
    thresholds: AccessibilityThresholds = Field(default_factory=AccessibilityThresholds)


class Ar5LandUseConfig(BaseModel):
    """Configuration for AR5 land use proximity scoring dimension."""

    enabled: bool = True
    industrial_buffer_m: float = 2000.0
    residential_buffer_m: float = 1000.0


class ScoringConfig(BaseModel):
    """Configuration for lake tentability scoring."""

    enabled: bool = False
    cabin_density: CabinDensityConfig = Field(default_factory=CabinDensityConfig)
    accessibility: AccessibilityConfig = Field(default_factory=AccessibilityConfig)
    ar5_land_use: Ar5LandUseConfig = Field(default_factory=Ar5LandUseConfig)


class Config(BaseModel):
    bbox: BBox | None = None
    fylke: str | None = None
    buffer_distance_m: float = 2000.0
    simplify_tolerance_m: float = 25.0
    min_lake_area_m2: float = 0.0
    data_dir: str = "data"
    output_dir: str = "output"
    output_filename: str = "map.html"
    landcover_mode: str = "wms"
    map: MapConfig = MapConfig()
    scoring: ScoringConfig = ScoringConfig()
    excluded_road_types: list[str] = Field(
        default_factory=lambda: ["P", "sti", "gangOgSykkelveg", "traktorveg"]
    )
    show_roads: bool = True
    lake_display_mode: Literal["polygon", "marker"] = "polygon"
    min_lake_tenting_quality: Literal["Terrible", "Poor", "Fair", "Good", "Excellent"] | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_fylke(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if "fylke" in data and "bbox" not in data:
            name = str(data["fylke"]).strip().lower()
            bbox = _FYLKE_BBOX.get(name)
            if bbox is None:
                available = ", ".join(sorted(_FYLKE_BBOX.keys()))
                raise ValueError(f"Unknown fylke '{name}'. Available: {available}")
            data["bbox"] = bbox.model_dump()
        return data

    @model_validator(mode="after")
    def require_bbox(self) -> "Config":
        if self.bbox is None:
            raise ValueError("Either 'bbox' or 'fylke' must be provided")
        return self

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def n50_path(self) -> Path:
        return self.data_path / "n50"


# Fylke bounding boxes in WGS84. Sourced from Kartverket kommuneinfo API.
# Keys are lowercase fylke names for case-insensitive lookup.
_FYLKE_BBOX: dict[str, BBox] = {
    "oslo":             BBox(north=60.1351, south=59.8093, east=10.9514, west=10.4892),
    "rogaland":         BBox(north=59.8446, south=58.0279, east=7.2147,  west=4.4543),
    "møre og romsdal":  BBox(north=63.7682, south=61.9233, east=9.3648,  west=4.8166),
    "nordland":         BBox(north=69.5967, south=64.9395, east=18.1514, west=10.5781),
    "østfold":          BBox(north=59.7703, south=58.7610, east=11.8298, west=10.5367),
    "akershus":         BBox(north=60.6051, south=59.4573, east=11.9460, west=10.1943),
    "buskerud":         BBox(north=61.0917, south=59.4079, east=10.6015, west=7.4388),
    "innlandet":        BBox(north=62.6969, south=59.8408, east=12.8708, west=7.3425),
    "vestfold":         BBox(north=59.6740, south=58.7205, east=10.6750, west=9.7553),
    "telemark":         BBox(north=60.1883, south=58.6033, east=9.9698,  west=7.0963),
    "agder":            BBox(north=59.6727, south=57.7590, east=9.6689,  west=6.1497),
    "vestland":         BBox(north=62.3824, south=59.4754, east=8.3221,  west=4.0875),
    "trøndelag":        BBox(north=65.4702, south=62.2557, east=14.3260, west=7.6481),
    "troms":            BBox(north=70.7036, south=68.3560, east=22.8945, west=15.5925),
    "finnmark":         BBox(north=71.3849, south=68.5546, east=31.7616, west=20.4797),
}


def load_config(path: str | Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config(**raw)
