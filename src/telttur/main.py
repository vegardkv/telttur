"""CLI entry point for telttur map generation."""

import math
import time

import click

from telttur.config import BBox, Profile, build_profile_config, dump_config_yaml, load_config
from telttur.data_export import export_data
from telttur.download import download_n50
from telttur.lakes import process_lakes
from telttur.roads import process_roads
from telttur.scoring import process_scoring
from telttur.scoring.cabin_density import extract_buildings_all


def _adaptive_simplify_tolerance(
    bbox: BBox, configured: float, large_threshold: float = 15_000, small_threshold: float = 2_000
) -> float:
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

    if area_km2 > large_threshold:
        minimum = 200.0
    elif area_km2 > small_threshold:
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
    default=None,
    type=click.Path(exists=True),
    help="Path to config YAML file.",
)
@click.option(
    "--profile",
    "profile",
    default=None,
    type=click.Choice(["local", "regional", "national"]),
    help="Use a built-in scale profile instead of a config file.",
)
@click.option("--skip-download", is_flag=True, help="Skip data download, use existing files.")
@click.option("--debug-buildings", is_flag=True, help=(
    "Export all raw building points for debugging. Not suitable for large regions."
))
def generate(
    config_path: str | None,
    profile: str | None,
    skip_download: bool,
    debug_buildings: bool,
) -> None:
    """Generate the camping suitability map."""
    if profile and config_path:
        raise click.UsageError("--profile and --config are mutually exclusive.")
    config = (
        build_profile_config(Profile(profile))
        if profile
        else load_config(config_path or "config.yaml")
    )
    assert config.bbox is not None  # guaranteed by Config.require_bbox validator
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

    # Step 2: Process roads (skip when not rendered and not needed for scoring)
    t0 = time.time()
    needs_roads = config.show_roads or (
        config.scoring.enabled and config.scoring.accessibility.enabled
    )
    if needs_roads:
        road_lines = process_roads(
            gdb_paths,
            config.bbox,
        )
        print(f"  [roads: {time.time() - t0:.1f}s]")
    else:
        import geopandas as gpd

        road_lines = gpd.GeoDataFrame()
        print("  [roads: skipped (not displayed and accessibility scoring disabled)]")

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
        )
        print(f"  [scoring: {time.time() - t0:.1f}s]")

    # Step 5: Export data.json
    t0 = time.time()
    print("Exporting data.json...")
    output_dir = config.output_path
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / config.output_filename

    debug_bldgs = None
    if debug_buildings:
        print("  Extracting all buildings for debug layer...")
        debug_bldgs = extract_buildings_all(gdb_paths, config.bbox)
        print(f"  Found {len(debug_bldgs)} building features")

    export_data(lakes, road_lines, config, output_file, debug_buildings=debug_bldgs)
    js_file = output_file.with_suffix(".js")
    js_kb = js_file.stat().st_size / 1024
    print(f"  [export: {time.time() - t0:.1f}s]")
    print(f"Data saved to: {js_file}  ({js_kb:.0f} KB)")

    if config.embed:
        from pathlib import Path

        from telttur.embed import embed_html

        stem = Path(config.output_filename).stem
        html_out = config.output_path / (stem.replace("data", "map", 1) + ".html")
        embed_html(Path("web"), js_file, html_out)
        print(f"Embedded HTML: {html_out}  ({html_out.stat().st_size / 1024:.0f} KB)")

    print(f"Total time: {time.time() - pipeline_start:.1f}s")


@cli.command()
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to config YAML file.",
)
def download(config_path: str | None) -> None:
    """Download N50 data only (no map generation)."""
    config = load_config(config_path or "config.yaml")
    config.data_path.mkdir(parents=True, exist_ok=True)
    assert config.bbox is not None  # guaranteed by Config.require_bbox validator
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


@cli.command()
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output path for the generated config YAML.",
)
@click.option(
    "--profile",
    "-p",
    default="local",
    type=click.Choice(["local", "regional", "national"]),
    show_default=True,
    help="Scale profile to use as the basis for the sample config.",
)
def sample(output: str, profile: str) -> None:
    """Generate a sample config YAML with all options filled in."""
    from pathlib import Path

    profile_type = Profile(profile)

    config = build_profile_config(profile_type)  # type: ignore[arg-type]
    yaml_text = dump_config_yaml(config, profile_type)  # type: ignore[arg-type]
    Path(output).write_text(yaml_text, encoding="utf-8")
    print(f"Sample config ({profile_type} profile) written to: {output}")
    print(f"Run with: uv run telttur generate --config {output}")
    print(f"       or: uv run telttur generate --profile {profile_type}")


if __name__ == "__main__":
    cli()
