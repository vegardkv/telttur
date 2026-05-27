"""Embed web/style.css and web/app.js inline into a single self-contained HTML file."""

from pathlib import Path


def embed_html(web_dir: Path, data_js_path: Path, output_path: Path) -> None:
    """Inline style.css, app.js, and the data file into a single HTML file.

    External CDN references (Leaflet, noUiSlider) are preserved as-is.
    Raises FileNotFoundError if any source file is missing.
    """
    html = (web_dir / "index.html").read_text(encoding="utf-8")
    css = (web_dir / "style.css").read_text(encoding="utf-8")
    app_js = (web_dir / "app.js").read_text(encoding="utf-8")
    data_js = data_js_path.read_text(encoding="utf-8")

    html = html.replace(
        '<link rel="stylesheet" href="style.css">',
        f"<style>\n{css}</style>",
    )
    html = html.replace(
        '<script src="../output/data.js"></script>',
        f"<script>\n{data_js}\n</script>",
    )
    html = html.replace(
        '<script src="app.js"></script>',
        f"<script>\n{app_js}\n</script>",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
