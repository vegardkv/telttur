"""CLI entry point for telttur map generation."""

import time
from pathlib import Path

import click

from telttur.config import load_config
from telttur.data_export import export_data
from telttur.download import download_n50
from telttur.lakes import process_lakes
from telttur.restrictions import tag_drinking_water
from telttur.roads import process_roads
from telttur.scoring import process_scoring
from telttur.scoring.cabin_density import extract_buildings_all


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
    "--debug-buildings",
    is_flag=True,
    help=("Export all raw building points for debugging. Not suitable for large regions."),
)
def generate(
    config_path: str | None,
    debug_buildings: bool,
) -> None:
    """Generate the camping suitability map."""
    config = load_config(config_path or "config.yaml")
    assert config.bbox is not None  # guaranteed by Config.require_bbox validator
    pipeline_start = time.time()

    print(
        f"Bounding box: N={config.bbox.north} S={config.bbox.south} "
        f"E={config.bbox.east} W={config.bbox.west}"
    )

    # Step 1: Download data
    t0 = time.time()
    config.data_path.mkdir(parents=True, exist_ok=True)
    gdb_paths = download_n50(config.bbox, config.data_path)
    if not gdb_paths:
        raise click.ClickException(
            "No data downloaded. Check your bounding box or network connection."
        )
    print(f"  [download/locate: {time.time() - t0:.1f}s]")

    # Step 2: Process roads (always needed for accessibility scoring)
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
        config.simplify_tolerance_m,
        min_lake_area_m2=config.min_lake_area_m2,
    )
    print(f"  [lakes: {time.time() - t0:.1f}s]")

    # Step 4: Tentability scoring
    if not lakes.empty:
        t0 = time.time()
        lakes = process_scoring(
            gdb_paths,
            config.bbox,
            lakes,
            road_lines,
            config.scoring,
            config.data_path,
        )
        print(f"  [scoring: {time.time() - t0:.1f}s]")

    # Step 5: Restriction flags (drinking-water source via Mattilsynet WMS)
    if not lakes.empty:
        t0 = time.time()
        print("Tagging drinking-water lakes (Mattilsynet WMS)...")
        lakes = tag_drinking_water(lakes, config.data_path)
        print(f"  [restrictions: {time.time() - t0:.1f}s]")

    # Step 6: Export data.json
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
        from telttur.embed import embed_html

        stem = Path(config.output_filename).stem
        html_out = config.output_path / (stem.replace("data", "map", 1) + ".html")
        embed_html(Path("web"), js_file, html_out)
        print(f"Embedded HTML: {html_out}  ({html_out.stat().st_size / 1024:.0f} KB)")

    print(f"Total time: {time.time() - pipeline_start:.1f}s")


if __name__ == "__main__":
    cli()
