"""Post-processing optimizations to reduce Folium HTML output size."""

from __future__ import annotations

import re

from telttur.config import OutputConfig


def optimize_html(html: str, config: OutputConfig) -> str:
    """Apply size-reduction transformations to a Folium-generated HTML string.

    Transformations applied (in order):
    1. Shorten Folium's MD5-based variable names to sequential short identifiers.
    2. Round floating-point numbers with 7+ decimal places to *coordinate_precision* decimals.
    3. Extract repeated popup inline styles to injected CSS classes.
    4. Strip whitespace: collapse blank lines, strip trailing spaces per line.

    Returns the optimized HTML string.
    """
    html = _shorten_variable_names(html)
    html = _reduce_coordinate_precision(html, config.coordinate_precision)
    html = _extract_popup_css(html)
    html = _strip_whitespace(html)
    return html


# ---------------------------------------------------------------------------
# Step 1: Variable name shortening
# ---------------------------------------------------------------------------

# Folium uses names like:  circle_marker_<32-hex>, popup_<32-hex>, html_<32-hex>,
# feature_group_<32-hex>, tile_layer_<32-hex>, map_<32-hex>,
# layer_control_<32-hex>, marker_cluster_<32-hex>.
# We replace each unique (prefix, hash) pair with a short sequential identifier.

_VAR_PATTERN = re.compile(
    r"\b(circle_marker|popup|html|feature_group|tile_layer|map|layer_control|marker_cluster)"
    r"_([0-9a-f]{32})\b"
)

_PREFIX_SHORT = {
    "circle_marker": "cm",
    "popup": "pp",
    "html": "ht",
    "feature_group": "fg",
    "tile_layer": "tl",
    "map": "mp",
    "layer_control": "lc",
    "marker_cluster": "mc",
}


def _shorten_variable_names(html: str) -> str:
    """Replace MD5-suffixed Folium variable names with short sequential identifiers.

    Uses a single-pass re.sub with a stateful callback — O(n) in file size.
    """
    counters: dict[str, int] = {}
    mapping: dict[str, str] = {}

    def _replace(m: re.Match[str]) -> str:
        full = m.group(0)
        if full not in mapping:
            prefix = m.group(1)
            short_prefix = _PREFIX_SHORT.get(prefix, prefix)
            idx = counters.get(short_prefix, 0)
            counters[short_prefix] = idx + 1
            mapping[full] = f"{short_prefix}{idx}"
        return mapping[full]

    return _VAR_PATTERN.sub(_replace, html)


# ---------------------------------------------------------------------------
# Step 2: Coordinate precision reduction
# ---------------------------------------------------------------------------

# Target: all floating-point literals with more decimal places than the
# configured precision.  Only touch numbers with 7+ digits after the decimal,
# which are overwhelmingly coordinates or other high-precision floats inserted
# by Folium/GeoJSON serialization.

_FLOAT_PATTERN = re.compile(r"(-?\d+\.\d{7,})")


def _reduce_coordinate_precision(html: str, precision: int) -> str:
    """Round all long floating-point literals to *precision* decimal places."""

    def _round_match(m: re.Match[str]) -> str:
        try:
            val = float(m.group(1))
            return f"{val:.{precision}f}"
        except ValueError:
            return m.group(0)

    return _FLOAT_PATTERN.sub(_round_match, html)


# ---------------------------------------------------------------------------
# Step 3: CSS class extraction for popup tables
# ---------------------------------------------------------------------------

# Folium embeds popup HTML as inline JavaScript strings. Every popup repeats
# the same table/cell inline styles.  We inject a tiny stylesheet and replace
# these repeated strings with class references.

_POPUP_CSS = (
    "<style>"
    ".tt-pw{width:100%;height:100%}"
    ".tt-pt{font-size:12px;border-collapse:collapse}"
    ".tt-ph{text-align:left;padding:2px 6px 2px 0}"
    ".tt-pd{padding:2px 0}"
    ".tt-hr{margin:3px 0;border:none;border-top:1px solid #ccc}"
    ".tt-b1{background:#d73027;color:white;padding:1px 6px;border-radius:3px;font-size:11px}"
    ".tt-b2{background:#fc8d59;color:white;padding:1px 6px;border-radius:3px;font-size:11px}"
    ".tt-b3{background:#fee08b;color:#333333;padding:1px 6px;border-radius:3px;font-size:11px}"
    ".tt-b4{background:#91cf60;color:white;padding:1px 6px;border-radius:3px;font-size:11px}"
    ".tt-b5{background:#1a9850;color:white;padding:1px 6px;border-radius:3px;font-size:11px}"
    "</style>"
)

# Ordered list of (old, new) string substitutions applied to the full HTML.
# Order matters: more specific patterns first.
_CSS_REPLACEMENTS: list[tuple[str, str]] = [
    # Popup div: width/height style (set by Folium's popup wrapper)
    (' style="width: 100.0%; height: 100.0%;"', ' class="tt-pw"'),
    # Table
    ("<table style='font-size:12px;border-collapse:collapse'>", "<table class='tt-pt'>"),
    # Header cells
    ("<th style='text-align:left;padding:2px 6px 2px 0'>", "<th class='tt-ph'>"),
    # Data cells
    ("<td style='padding:2px 0'>", "<td class='tt-pd'>"),
    # Separator rule
    ("<hr style='margin:3px 0;border:none;border-top:1px solid #ccc'>", "<hr class='tt-hr'>"),
    # Score badge spans — by fill color
    (
        "style='background:#d73027;color:white;padding:1px 6px;border-radius:3px;font-size:11px'",
        "class='tt-b1'",
    ),
    (
        "style='background:#fc8d59;color:white;padding:1px 6px;border-radius:3px;font-size:11px'",
        "class='tt-b2'",
    ),
    (
        "style='background:#fee08b;color:#333333;padding:1px 6px;border-radius:3px;font-size:11px'",
        "class='tt-b3'",
    ),
    (
        "style='background:#91cf60;color:white;padding:1px 6px;border-radius:3px;font-size:11px'",
        "class='tt-b4'",
    ),
    (
        "style='background:#1a9850;color:white;padding:1px 6px;border-radius:3px;font-size:11px'",
        "class='tt-b5'",
    ),
]


def _extract_popup_css(html: str) -> str:
    """Inject a stylesheet and replace repeated popup inline styles with class references."""
    # Only inject CSS if any of the target strings are present.
    if "<table style='font-size:12px" not in html:
        return html

    # Apply all string substitutions.
    for old, new in _CSS_REPLACEMENTS:
        html = html.replace(old, new)

    # Inject the stylesheet just before </head>.
    html = html.replace("</head>", _POPUP_CSS + "</head>", 1)
    return html


# ---------------------------------------------------------------------------
# Step 4: Whitespace stripping
# ---------------------------------------------------------------------------


def _strip_whitespace(html: str) -> str:
    """Strip trailing whitespace per line and collapse runs of blank lines to one."""
    lines = html.splitlines()
    result: list[str] = []
    prev_blank = False
    for line in lines:
        stripped = line.rstrip()
        is_blank = stripped == ""
        if is_blank and prev_blank:
            continue  # collapse consecutive blank lines
        result.append(stripped)
        prev_blank = is_blank
    return "\n".join(result)
