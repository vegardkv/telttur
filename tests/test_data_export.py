"""Tests for the data.js export helpers."""

import geopandas as gpd
from shapely.geometry import Polygon

from telttur.data_export import _compute_density_quantiles, build_lake_data
from telttur.geo import CRS_WGS84
from telttur.lakes import LakeCols


def _square(lng: float, lat: float, size: float = 0.01) -> Polygon:
    return Polygon([(lng, lat), (lng + size, lat), (lng + size, lat + size), (lng, lat + size)])


def _lakes_gdf(**columns) -> gpd.GeoDataFrame:
    geometry = [_square(10.0, 60.0), _square(10.5, 60.5)]
    return gpd.GeoDataFrame(columns, geometry=geometry, crs=CRS_WGS84)


class TestComputeDensityQuantiles:
    def test_missing_column_falls_back_to_linear_range(self) -> None:
        lakes = _lakes_gdf()
        qs = _compute_density_quantiles(lakes, steps=5)
        assert len(qs) == 5
        assert qs[-1] == 0.15

    def test_all_zero_densities_fall_back(self) -> None:
        lakes = _lakes_gdf(**{LakeCols.BUILDING_DENSITY: [0.0, 0.0]})
        qs = _compute_density_quantiles(lakes, steps=4)
        assert len(qs) == 4
        assert qs[-1] == 0.15

    def test_nonzero_densities_give_zero_then_quantiles(self) -> None:
        lakes = gpd.GeoDataFrame(
            {LakeCols.BUILDING_DENSITY: [0.0, 0.1, 0.2, 0.3, 0.4]},
            geometry=[_square(10.0 + i * 0.1, 60.0) for i in range(5)],
            crs=CRS_WGS84,
        )
        qs = _compute_density_quantiles(lakes, steps=5)
        assert len(qs) == 5
        assert qs[0] == 0.0
        assert qs == sorted(qs)  # monotonically increasing
        assert qs[-1] == 0.4  # 100th percentile of the non-zero values


class TestBuildLakeData:
    def test_rows_align_with_field_names(self) -> None:
        lakes = _lakes_gdf(
            **{
                LakeCols.AREA_M2: [1000.0, 2000.0],
                LakeCols.ROAD_DISTANCE_M: [150.0, 250.0],
                LakeCols.FISH_GENERA_MASK: [3, 0],
            }
        )
        rows, fields = build_lake_data(lakes)

        assert len(rows) == 2
        assert fields[:3] == ["lat", "lng", "area"]
        assert set(fields[3:]) == {LakeCols.FISH_GENERA_MASK, LakeCols.ROAD_DISTANCE_M}

        row = rows[0]
        assert len(row) == len(fields)
        assert row[fields.index("area")] == 1000.0
        assert row[fields.index(LakeCols.ROAD_DISTANCE_M)] == 150.0
        assert row[fields.index(LakeCols.FISH_GENERA_MASK)] == 3

    def test_mask_fields_are_ints_distances_are_floats(self) -> None:
        lakes = _lakes_gdf(
            **{
                LakeCols.AREA_M2: [1000.0, 2000.0],
                LakeCols.ROAD_DISTANCE_M: [150.06, 250.0],
                LakeCols.FISH_GENERA_MASK: [3.0, 0.0],  # float input must export as int
            }
        )
        rows, fields = build_lake_data(lakes)
        mask_val = rows[0][fields.index(LakeCols.FISH_GENERA_MASK)]
        dist_val = rows[0][fields.index(LakeCols.ROAD_DISTANCE_M)]
        assert isinstance(mask_val, int)
        assert dist_val == 150.1  # rounded to 1 dp

    def test_name_column_is_last_field(self) -> None:
        lakes = _lakes_gdf(
            **{
                LakeCols.AREA_M2: [1000.0, 2000.0],
                "navn": ["Storsjøen", None],
            }
        )
        rows, fields = build_lake_data(lakes)
        assert fields[-1] == "name"
        assert rows[0][-1] == "Storsjøen"
        assert rows[1][-1] is None

    def test_lat_lng_are_inside_lake_polygon(self) -> None:
        lakes = _lakes_gdf(**{LakeCols.AREA_M2: [1000.0, 2000.0]})
        rows, fields = build_lake_data(lakes)
        lat, lng = rows[0][0], rows[0][1]
        assert 60.0 <= lat <= 60.01
        assert 10.0 <= lng <= 10.01
