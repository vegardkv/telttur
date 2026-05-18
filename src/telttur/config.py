from enum import Enum
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

    excellent: float = 0.0  # pristine: no buildings at all
    good: float = 0.01  # e.g. ≤3 buildings around a 90 000 m² lake
    fair: float = 0.05  # e.g. ≤5 buildings around a 10 000 m² lake
    poor: float = 0.15  # above this → Terrible


class AccessibilityThresholds(BaseModel):
    """Distance thresholds (metres) for accessibility scoring (upper bound per level).

    A lake receives a level if its road_distance_m is <= the threshold for that level.
    Lakes farther than the 'poor' threshold are scored Terrible.
    """

    excellent: float = 500.0  # < 500 m  → Excellent
    good: float = 1000.0  # < 1 km   → Good
    fair: float = 2000.0  # < 2 km   → Fair
    poor: float = 5000.0  # < 5 km   → Poor; ≥ 5 km → Terrible


class InteractiveDimensionToggles(BaseModel):
    """Which scoring dimension checkboxes to expose in the interactive panel."""

    cabin_density: bool = True
    accessibility: bool = True
    ar5_land_use: bool = True
    fishing: bool = True


class InteractiveAccessibilityRange(BaseModel):
    """Range slider config for interactive accessibility scoring."""

    enabled: bool = True
    min_m: float = 200.0  # default preferred minimum distance
    max_m: float = 2000.0  # default preferred maximum distance
    slider_max_m: float = 10000.0  # upper bound of the slider


class InteractiveCabinDensityThresholds(BaseModel):
    """Which cabin density threshold sliders to expose."""

    excellent: bool = False
    good: bool = False
    fair: bool = False
    poor: bool = False


class InteractiveControlsConfig(BaseModel):
    """Configuration for the interactive scoring controls panel embedded in the map."""

    enabled: bool = True
    dimension_toggles: InteractiveDimensionToggles = Field(
        default_factory=InteractiveDimensionToggles
    )
    min_lake_area: bool = True
    accessibility_range: InteractiveAccessibilityRange = Field(
        default_factory=InteractiveAccessibilityRange
    )
    cabin_density_thresholds: InteractiveCabinDensityThresholds = Field(
        default_factory=InteractiveCabinDensityThresholds
    )


class MapConfig(BaseModel):
    """Configuration for map rendering options."""

    include_osm_layer: bool = False
    use_marker_cluster: bool = False
    base_map: Literal["greyscale", "topographic", "selectable"] = "greyscale"
    interactive_controls: InteractiveControlsConfig = Field(
        default_factory=InteractiveControlsConfig
    )


class CabinDensityConfig(BaseModel):
    """Configuration for cabin density scoring dimension."""

    enabled: bool = True
    buffer_m: float = 200.0
    thresholds: CabinDensityThresholds = Field(default_factory=CabinDensityThresholds)


class AccessibilityConfig(BaseModel):
    """Configuration for accessibility scoring dimension."""

    enabled: bool = True
    excluded_road_types: list[str] = Field(
        default_factory=lambda: ["P", "sti", "gangOgSykkelveg", "traktorveg"]
    )
    thresholds: AccessibilityThresholds = Field(default_factory=AccessibilityThresholds)


class Ar5DataSource(str, Enum):
    """Data source to use for AR5 land use polygons."""

    AUTO = "auto"  # try WFS first, fall back to N50 on failure
    WFS = "wfs"  # always use the NIBIO AR5 WFS (raise on failure)
    N50 = "n50"  # always use the local N50 arealdekke data


class Ar5LandUseConfig(BaseModel):
    """Configuration for AR5 land use proximity scoring dimension."""

    enabled: bool = True
    source: Ar5DataSource = Ar5DataSource.AUTO
    industrial_buffer_m: float = 2000.0
    residential_buffer_m: float = 1000.0


class FishingConfig(BaseModel):
    """Configuration for fishing suitability scoring dimension."""

    enabled: bool = True
    buffer_m: float = 500.0


class ScoringConfig(BaseModel):
    """Configuration for lake tentability scoring."""

    enabled: bool = True
    cabin_density: CabinDensityConfig = Field(default_factory=CabinDensityConfig)
    accessibility: AccessibilityConfig = Field(default_factory=AccessibilityConfig)
    ar5_land_use: Ar5LandUseConfig = Field(default_factory=Ar5LandUseConfig)
    fishing: FishingConfig = Field(default_factory=FishingConfig)


class Config(BaseModel):
    bbox: BBox | None = None
    fylke: str | None = None
    buffer_distance_m: float = 2000.0
    simplify_tolerance_m: float = 25.0
    min_lake_area_m2: float = 0.0
    data_dir: str = "data"
    output_dir: str = "output"
    output_filename: str = "map.html"
    landcover_mode: Literal["wms", "vector", "disabled"] = "wms"
    map: MapConfig = MapConfig()
    scoring: ScoringConfig = ScoringConfig()
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
    "oslo": BBox(north=60.1351, south=59.8093, east=10.9514, west=10.4892),
    "rogaland": BBox(north=59.8446, south=58.0279, east=7.2147, west=4.4543),
    "møre og romsdal": BBox(north=63.7682, south=61.9233, east=9.3648, west=4.8166),
    "nordland": BBox(north=69.5967, south=64.9395, east=18.1514, west=10.5781),
    "østfold": BBox(north=59.7703, south=58.7610, east=11.8298, west=10.5367),
    "akershus": BBox(north=60.6051, south=59.4573, east=11.9460, west=10.1943),
    "buskerud": BBox(north=61.0917, south=59.4079, east=10.6015, west=7.4388),
    "innlandet": BBox(north=62.6969, south=59.8408, east=12.8708, west=7.3425),
    "vestfold": BBox(north=59.6740, south=58.7205, east=10.6750, west=9.7553),
    "telemark": BBox(north=60.1883, south=58.6033, east=9.9698, west=7.0963),
    "agder": BBox(north=59.6727, south=57.7590, east=9.6689, west=6.1497),
    "vestland": BBox(north=62.3824, south=59.4754, east=8.3221, west=4.0875),
    "trøndelag": BBox(north=65.4702, south=62.2557, east=14.3260, west=7.6481),
    "troms": BBox(north=70.7036, south=68.3560, east=22.8945, west=15.5925),
    "finnmark": BBox(north=71.3849, south=68.5546, east=31.7616, west=20.4797),
    # Whole country
    "norway": BBox(north=71.5, south=57.7, east=31.8, west=4.0),
}


def load_config(path: str | Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config(**raw)


# ---------------------------------------------------------------------------
# Profile system
# ---------------------------------------------------------------------------

Profile = Literal["local", "regional", "national"]


def build_profile_config(profile: Profile) -> Config:
    """Build a Config from a named profile with sensible scale-based defaults."""
    if profile == "local":
        return Config(
            fylke="oslo",
            min_lake_area_m2=1000.0,
            lake_display_mode="polygon",
            landcover_mode="wms",
            show_roads=True,
            map=MapConfig(
                use_marker_cluster=False,
                interactive_controls=InteractiveControlsConfig(enabled=True),
            ),
            scoring=ScoringConfig(
                accessibility=AccessibilityConfig(enabled=True),
                ar5_land_use=Ar5LandUseConfig(enabled=True),
            ),
        )
    elif profile == "regional":
        return Config(
            fylke="akershus",
            min_lake_area_m2=1000.0,
            lake_display_mode="marker",
            landcover_mode="wms",
            show_roads=False,
            min_lake_tenting_quality="Fair",
            map=MapConfig(
                use_marker_cluster=False,
                interactive_controls=InteractiveControlsConfig(enabled=True),
            ),
            scoring=ScoringConfig(
                accessibility=AccessibilityConfig(enabled=True),
                ar5_land_use=Ar5LandUseConfig(enabled=True),
            ),
        )
    else:  # national
        return Config(
            fylke="norway",
            min_lake_area_m2=50000.0,
            lake_display_mode="marker",
            landcover_mode="disabled",
            show_roads=False,
            min_lake_tenting_quality="Fair",
            map=MapConfig(
                use_marker_cluster=True,
                interactive_controls=InteractiveControlsConfig(enabled=False),
            ),
            scoring=ScoringConfig(
                accessibility=AccessibilityConfig(enabled=False),
                ar5_land_use=Ar5LandUseConfig(enabled=False),
            ),
        )


def _convert_enums(obj: object) -> object:
    """Recursively replace Enum instances with their .value in a nested structure."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _convert_enums(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_enums(item) for item in obj]
    return obj


def dump_config_yaml(config: Config, profile: Profile | None = None) -> str:
    """Serialise *config* to a YAML string suitable for use as a config file.

    The derived ``bbox`` field is excluded because it is resolved automatically
    from ``fylke`` at load time. Enum values are serialised as plain strings.
    A header comment is prepended indicating the profile (if any).
    """
    data = config.model_dump(mode="python")
    data.pop("bbox", None)  # derived from fylke; not needed in the file
    data = _convert_enums(data)  # type: ignore[assignment]

    header_lines = ["# Generated by: uv run telttur sample"]
    if profile:
        header_lines.append(f"# Profile: {profile}")
    header_lines.append(
        "# Run with: uv run telttur generate --config <this-file>"
        f"{f' (or: --profile {profile})' if profile else ''}"
    )
    header = "\n".join(header_lines) + "\n\n"

    return header + yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
