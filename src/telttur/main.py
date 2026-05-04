"""CLI entry point for telttur map generation."""

import math
import time

import click

from telttur.config import BBox, load_config
from telttur.download import download_n50
from telttur.lakes import process_lakes
from telttur.landcover import process_landcover
from telttur.map_generator import generate_map, save_map
from telttur.roads import process_roads
from telttur.scoring import process_scoring


def _adaptive_simplify_tolerance(bbox: BBox, configured: float) -> float:
    """Return an effective simplify tolerance based on bbox area.

    Thresholds (km²):
      <  2 000 km² — use configured value as-is
      2 000–15 000 km² — at least 100 m
      > 15 000 km² — at least 200 m
    """
    lat_km = (bbox.north - bbox.south) * 111.0
    mid_lat_rad = math.radians((bbox.north + bbox.south) / 2)
    lon_km = (bbox.east - bbox.west) * 111.0 * math.cos(mid_lat_rad)
    area_km2 = lat_km * lon_km

    if area_km2 > 15_000:
        minimum = 200.0
    elif area_km2 > 2_000:
        minimum = 100.0
    else:
        minimum = configured

    effective = max(configured, minimum)
    if effective != configured:
        print(
            f"Adaptive simplification: bbox area ~{area_km2:.0f} km², "
            f"raising tolerance from {configured}m to {effective}m"
        )
    return effective


@click.group()
def cli() -> None:
    """Telttur - Norwegian camping suitability map generator."""


@cli.command()
@click.option(
    "--config",
    "config_path",
    default="config.yaml",
    type=click.Path(exists=True),
    help="Path to config YAML file.",
)
@click.option("--skip-download", is_flag=True, help="Skip data download, use existing files.")
def generate(config_path: str, skip_download: bool) -> None:
    """Generate the camping suitability map."""
    config = load_config(config_path)
    pipeline_start = time.time()

    print(
        f"Bounding box: N={config.bbox.north} S={config.bbox.south} "
        f"E={config.bbox.east} W={config.bbox.west}"
    )
    print(f"Buffer distance: {config.buffer_distance_m}m")
    print(f"Land cover mode: {config.landcover_mode}")

    effective_simplify = _adaptive_simplify_tolerance(config.bbox, config.simplify_tolerance_m)

    # Step 1: Download data
    t0 = time.time()
    if skip_download:
        # Find existing .gdb files
        n50_dir = config.n50_path
        gdb_paths = list(n50_dir.rglob("*.gdb")) if n50_dir.exists() else []
        if not gdb_paths:
            raise click.ClickException(
                f"No .gdb files found in {n50_dir}. Run without --skip-download first."
            )
        print(f"Using {len(gdb_paths)} existing .gdb file(s)")
    else:
        config.data_path.mkdir(parents=True, exist_ok=True)
        gdb_paths = download_n50(config.bbox, config.data_path)
        if not gdb_paths:
            raise click.ClickException(
                "No data downloaded. Check your bounding box or network connection."
            )
    print(f"  [download/locate: {time.time() - t0:.1f}s]")

    # Step 2: Process roads
    t0 = time.time()
    road_lines = process_roads(
        gdb_paths,
        config.bbox,
    )
    print(f"  [roads: {time.time() - t0:.1f}s]")

    # Step 3: Process lakes
    t0 = time.time()
    lakes = process_lakes(
        gdb_paths,
        config.bbox,
        effective_simplify,
        min_lake_area_m2=config.min_lake_area_m2,
    )
    print(f"  [lakes: {time.time() - t0:.1f}s]")

    # Step 4: Tentability scoring (optional)
    if config.scoring.enabled and not lakes.empty:
        t0 = time.time()
        lakes = process_scoring(
            gdb_paths,
            config.bbox,
            lakes,
            road_lines,
            config.scoring,
            excluded_road_types=config.excluded_road_types,
        )
        print(f"  [scoring: {time.time() - t0:.1f}s]")

    # Filter lakes by minimum tenting level
    if (
        config.min_lake_tenting_quality is not None
        and not lakes.empty
        and "tentability_level" in lakes.columns
    ):
        before = len(lakes)
        from telttur.scoring import LEVEL_NAMES
        _level_by_name = {v: k for k, v in LEVEL_NAMES.items()}
        min_score = _level_by_name[config.min_lake_tenting_quality]
        lakes = lakes[lakes["tentability_score"] >= min_score].reset_index(drop=True)
        print(
            f"  [lake filter: kept {len(lakes)}/{before} lakes"
            f" with tenting level >= {config.min_lake_tenting_quality}]"
        )

    # Step 5: Land cover (vector mode only; WMS is added directly in map generator)
    landcover = None
    if config.landcover_mode == "vector":
        t0 = time.time()
        landcover = process_landcover(
            gdb_paths,
            config.bbox,
            effective_simplify,
        )
        print(f"  [landcover: {time.time() - t0:.1f}s]")

    # Step 6: Generate map
    t0 = time.time()
    print("Generating map...")
    m = generate_map(
        config,
        road_lines,
        lakes,
        landcover=landcover,
        landcover_mode=config.landcover_mode,
    )
    output_path = save_map(m, config)
    print(f"  [map render+save: {time.time() - t0:.1f}s]")
    print(f"Map saved to: {output_path}")
    print(f"Total time: {time.time() - pipeline_start:.1f}s")


@cli.command()
@click.option(
    "--config",
    "config_path",
    default="config.yaml",
    type=click.Path(exists=True),
    help="Path to config YAML file.",
)
def download(config_path: str) -> None:
    """Download N50 data only (no map generation)."""
    config = load_config(config_path)
    config.data_path.mkdir(parents=True, exist_ok=True)

    gdb_paths = download_n50(config.bbox, config.data_path)
    print(f"Downloaded {len(gdb_paths)} .gdb file(s)")
    for p in gdb_paths:
        print(f"  {p}")


@cli.command()
@click.argument("gdb_path", type=click.Path(exists=True))
def inspect(gdb_path: str) -> None:
    """Inspect layers in a .gdb file."""
    import fiona

    layers = fiona.listlayers(gdb_path)
    print(f"Layers in {gdb_path}:")
    for layer in sorted(layers):
        with fiona.open(gdb_path, layer=layer) as src:
            props = list(src.schema["properties"].keys())[:8]
            print(f"  {layer}: {len(src)} features, schema: {props}")


if __name__ == "__main__":
    cli()
