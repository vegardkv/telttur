"""CLI entry point for telttur map generation."""

import click

from telttur.config import load_config
from telttur.download import download_n50
from telttur.lake_classification import process_lake_classification
from telttur.lakes import process_lakes
from telttur.landcover import process_landcover
from telttur.map_generator import generate_map, save_map
from telttur.roads import process_roads


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

    print(
        f"Bounding box: N={config.bbox.north} S={config.bbox.south} "
        f"E={config.bbox.east} W={config.bbox.west}"
    )
    print(f"Buffer distance: {config.buffer_distance_m}m")
    print(f"Land cover mode: {config.landcover_mode}")

    # Step 1: Download data
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

    # Step 2: Process roads
    road_buffers = process_roads(
        gdb_paths,
        config.bbox,
        config.buffer_distance_m,
        config.simplify_tolerance_m,
    )

    # Step 3: Process lakes
    lakes = process_lakes(
        gdb_paths,
        config.bbox,
        config.simplify_tolerance_m,
        road_buffers=road_buffers,
    )

    # Step 4: Lake classification (optional)
    if config.lake_classification.enabled and not lakes.empty:
        lakes = process_lake_classification(
            gdb_paths,
            config.bbox,
            lakes,
            config.lake_classification.building_buffer_m,
        )

    # Step 5: Land cover (vector mode only; WMS is added directly in map generator)
    landcover = None
    if config.landcover_mode == "vector":
        landcover = process_landcover(
            gdb_paths,
            config.bbox,
            config.simplify_tolerance_m,
        )

    # Step 6: Generate map
    print("Generating map...")
    m = generate_map(
        config,
        road_buffers,
        lakes,
        landcover=landcover,
        landcover_mode=config.landcover_mode,
    )
    output_path = save_map(m, config)
    print(f"Map saved to: {output_path}")


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
