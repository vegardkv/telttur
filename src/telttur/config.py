from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class BBox(BaseModel):
    north: float
    south: float
    east: float
    west: float


class InteractiveAccessibilityRange(BaseModel):
    """Range slider config for interactive accessibility scoring."""

    min_m: float = 0.0  # default preferred minimum distance
    max_m: float = 2000.0  # default preferred maximum distance
    slider_max_m: float = 10000.0  # upper bound of the slider


class InteractiveCabinDensitySlider(BaseModel):
    """Discrete stepped slider for cabin density tolerance.

    The slider has *steps* discrete positions whose thresholds are derived from
    the quantile distribution of ``building_density`` across all lakes in the
    export.  This gives users an intuitive "Low → High" tolerance control
    rather than a raw density number.
    """

    steps: int = 5  # number of discrete slider positions
    default_step: int = 3  # 1-indexed default position


class InteractiveAr5Buffers(BaseModel):
    """Sliders for AR5 residential and industrial proximity buffer distances.

    One slider per zone type is shown.  Within the buffer = Terrible;
    beyond 2× the buffer = Excellent, with gradual steps in between.
    """

    slider_max_m: float = 10000.0


class InteractiveClimb(BaseModel):
    """Max acceptable vertical climb slider in the accessibility card.

    Climb beyond max_m tapers the accessibility score toward Elendig (1)
    following the same shape as the other dimension sliders.
    """

    max_m: float = 200.0
    slider_max_m: float = 1000.0


class InteractiveControlsConfig(BaseModel):
    """Configuration for the interactive scoring controls panel embedded in the map."""

    accessibility_range: InteractiveAccessibilityRange = Field(
        default_factory=InteractiveAccessibilityRange
    )
    cabin_density_slider: InteractiveCabinDensitySlider = Field(
        default_factory=InteractiveCabinDensitySlider
    )
    ar5_buffers: InteractiveAr5Buffers = Field(default_factory=InteractiveAr5Buffers)
    climb: InteractiveClimb = Field(default_factory=InteractiveClimb)


class MapConfig(BaseModel):
    """Configuration for map rendering options."""

    interactive_controls: InteractiveControlsConfig = Field(
        default_factory=InteractiveControlsConfig
    )


class CabinDensityConfig(BaseModel):
    """Configuration for cabin density scoring dimension."""

    buffer_m: float = 200.0


class AccessibilityConfig(BaseModel):
    """Configuration for accessibility scoring dimension."""

    excluded_road_types: list[str] = Field(
        default_factory=lambda: ["P", "sti", "gangOgSykkelveg", "traktorveg"]
    )


class Ar5DataSource(StrEnum):
    """Data source to use for AR5 land use polygons."""

    AUTO = "auto"  # try WFS first, fall back to N50 on failure
    WFS = "wfs"  # always use the NIBIO AR5 WFS (raise on failure)
    N50 = "n50"  # always use the local N50 arealdekke data


class Ar5LandUseConfig(BaseModel):
    """Configuration for AR5 land use proximity scoring dimension."""

    source: Ar5DataSource = Ar5DataSource.AUTO
    industrial_buffer_m: float = 2000.0
    residential_buffer_m: float = 1000.0


class FishingConfig(BaseModel):
    """Configuration for fishing suitability scoring dimension."""

    buffer_m: float = 500.0


class ScoringConfig(BaseModel):
    """Configuration for lake tentability scoring."""

    cabin_density: CabinDensityConfig = Field(default_factory=CabinDensityConfig)
    accessibility: AccessibilityConfig = Field(default_factory=AccessibilityConfig)
    ar5_land_use: Ar5LandUseConfig = Field(default_factory=Ar5LandUseConfig)
    fishing: FishingConfig = Field(default_factory=FishingConfig)


class Config(BaseModel):
    bbox: BBox | None = None
    fylke: str | None = None
    simplify_tolerance_m: float = 25.0
    min_lake_area_m2: float = 0.0
    data_dir: str = "data"
    output_dir: str = "output"
    output_filename: str = "data.js"
    embed: bool = False
    map: MapConfig = MapConfig()
    scoring: ScoringConfig = ScoringConfig()
    show_roads: bool = True
    debug_map: bool = False

    @model_validator(mode="before")
    @classmethod
    def resolve_fylke(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if "fylke" in data and "bbox" not in data:
            name = str(data["fylke"]).strip().lower()  # ty: ignore[invalid-argument-type]
            table = _fylke_bbox_table()
            bbox = table.get(name)
            if bbox is None:
                available = ", ".join(sorted(table.keys()))
                raise ValueError(f"Unknown fylke '{name}'. Available: {available}")
            data["bbox"] = bbox.model_dump()  # ty: ignore[invalid-assignment]
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


def _fylke_bbox_table() -> dict[str, BBox]:
    """Name→bbox lookup derived from download.FYLKE_BOUNDS (the single source of truth).

    Keys are lowercase fylke names for case-insensitive lookup, plus the special
    "norway" entry covering the whole country. Imported lazily because
    download.py imports this module at top level.
    """
    from telttur.download import FYLKE_BOUNDS

    table = {
        name.lower(): BBox(north=n, south=s, east=e, west=w)
        for name, (s, w, n, e) in FYLKE_BOUNDS.values()
    }
    table["norway"] = BBox(north=71.5, south=57.7, east=31.8, west=4.0)
    return table


def load_config(path: str) -> Config:
    with Path(path).open() as f:
        raw = yaml.safe_load(f)
    return Config(**raw)
