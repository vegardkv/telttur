"""Tests for bbox/fylke overlap detection."""

from telttur.config import BBox
from telttur.download import _bbox_overlaps

# Fylke-style bounds tuple: (south, west, north, east)
_BOUNDS = (59.0, 10.0, 60.0, 11.0)


def test_overlapping_bbox() -> None:
    bbox = BBox(north=59.7, south=59.3, east=10.7, west=10.3)
    assert _bbox_overlaps(bbox, _BOUNDS)


def test_bbox_containing_bounds_overlaps() -> None:
    bbox = BBox(north=61.0, south=58.0, east=12.0, west=9.0)
    assert _bbox_overlaps(bbox, _BOUNDS)


def test_disjoint_north() -> None:
    bbox = BBox(north=62.0, south=61.0, east=10.7, west=10.3)
    assert not _bbox_overlaps(bbox, _BOUNDS)


def test_disjoint_east() -> None:
    bbox = BBox(north=59.7, south=59.3, east=13.0, west=12.0)
    assert not _bbox_overlaps(bbox, _BOUNDS)


def test_touching_edge_counts_as_overlap() -> None:
    bbox = BBox(north=59.5, south=59.0, east=10.0, west=9.0)  # east edge == west bound
    assert _bbox_overlaps(bbox, _BOUNDS)
