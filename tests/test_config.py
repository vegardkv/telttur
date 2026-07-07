"""Tests for config loading and validation."""

import pytest
from pydantic import ValidationError

from telttur.config import BBox, Config, load_config


def test_fylke_resolves_to_bbox() -> None:
    config = Config(fylke="Innlandet")
    assert config.bbox is not None
    assert config.bbox.north == pytest.approx(62.6969)
    assert config.bbox.west == pytest.approx(7.3425)


def test_fylke_lookup_is_case_insensitive() -> None:
    upper = Config(fylke="AKERSHUS")
    lower = Config(fylke="akershus")
    assert upper.bbox == lower.bbox


def test_unknown_fylke_raises_with_available_names() -> None:
    with pytest.raises(ValidationError, match="Unknown fylke"):
        Config(fylke="atlantis")


def test_explicit_bbox_wins_over_fylke() -> None:
    bbox = BBox(north=61.0, south=60.0, east=10.0, west=9.0)
    config = Config(bbox=bbox, fylke="Innlandet")
    assert config.bbox == bbox


def test_missing_bbox_and_fylke_raises() -> None:
    with pytest.raises(ValidationError, match="Either 'bbox' or 'fylke'"):
        Config()


def test_load_config_reads_yaml(tmp_path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("fylke: Oslo\nmin_lake_area_m2: 5000\n")
    config = load_config(str(path))
    assert config.bbox is not None
    assert config.min_lake_area_m2 == 5000
