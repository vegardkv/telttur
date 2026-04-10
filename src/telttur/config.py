from pathlib import Path

import yaml
from pydantic import BaseModel


class BBox(BaseModel):
    north: float
    south: float
    east: float
    west: float


class LakeClassification(BaseModel):
    enabled: bool = False
    building_buffer_m: float = 500.0


class Config(BaseModel):
    bbox: BBox
    buffer_distance_m: float = 2000.0
    simplify_tolerance_m: float = 50.0
    data_dir: str = "data"
    output_dir: str = "output"
    output_filename: str = "map.html"
    landcover_mode: str = "wms"
    lake_classification: LakeClassification = LakeClassification()

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def n50_path(self) -> Path:
        return self.data_path / "n50"


def load_config(path: str | Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config(**raw)
