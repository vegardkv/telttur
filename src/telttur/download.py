"""Download N50 Kartdata from Geonorge download API."""

import zipfile
from pathlib import Path

import requests
from pydantic import BaseModel
from pydantic import BaseModel
from tqdm import tqdm

from telttur.config import BBox

class OrderFile(BaseModel):
    name: str
    status: str
    downloadUrl: str


class OrderReceipt(BaseModel):
    files: list[OrderFile] = []


N50_METADATA_UUID = "ea192681-d039-42ec-b1bc-f3ce04c189ac"
GEONORGE_API_BASE = "https://nedlasting.geonorge.no/api"
TARGET_FORMAT = "FGDB"
TARGET_PROJECTION = "25833"  # EUREF89 UTM sone 33

# Norwegian fylke bounding boxes (WGS84 / EPSG:4258, sourced from Kartverket kommuneinfo API)
# Used to determine which fylke(r) overlap a user's bbox
# Generated from: https://ws.geonorge.no/kommuneinfo/v1/fylker/{code}
FYLKE_BOUNDS: dict[str, tuple[str, tuple[float, float, float, float]]] = {
    # code: (name, (south, west, north, east))
    "03": ("Oslo", (59.8093, 10.4892, 60.1351, 10.9514)),
    "11": ("Rogaland", (58.0279, 4.4543, 59.8446, 7.2147)),
    "15": ("Møre og Romsdal", (61.9233, 4.8166, 63.7682, 9.3648)),
    "18": ("Nordland", (64.9395, 10.5781, 69.5967, 18.1514)),
    "31": ("Østfold", (58.7610, 10.5367, 59.7703, 11.8298)),
    "32": ("Akershus", (59.4573, 10.1943, 60.6051, 11.9460)),
    "33": ("Buskerud", (59.4079, 7.4388, 61.0917, 10.6015)),
    "34": ("Innlandet", (59.8408, 7.3425, 62.6969, 12.8708)),
    "39": ("Vestfold", (58.7205, 9.7553, 59.6740, 10.6750)),
    "40": ("Telemark", (58.6033, 7.0963, 60.1883, 9.9698)),
    "42": ("Agder", (57.7590, 6.1497, 59.6727, 9.6689)),
    "46": ("Vestland", (59.4754, 4.0875, 62.3824, 8.3221)),
    "50": ("Trøndelag", (62.2557, 7.6481, 65.4702, 14.3260)),
    "55": ("Troms", (68.3560, 15.5925, 70.7036, 22.8945)),
    "56": ("Finnmark", (68.5546, 20.4797, 71.3849, 31.7616)),
}

KOMMUNEINFO_API = "https://ws.geonorge.no/kommuneinfo/v1/fylker"
_fylke_bounds_cache: dict[str, dict[str, tuple[str, tuple[float, float, float, float]]]] = {}


def get_fylke_bounds(
    use_cache: bool = True,
) -> dict[str, tuple[str, tuple[float, float, float, float]]]:
    """Return fylke bounding boxes, fetching from Kartverket API if not cached.

    Falls back to the hardcoded FYLKE_BOUNDS if the API is unavailable.
    Result format: {code: (name, (south, west, north, east))}
    """
    if use_cache and "data" in _fylke_bounds_cache:
        return _fylke_bounds_cache["data"]

    try:
        resp = requests.get(KOMMUNEINFO_API, timeout=10)
        resp.raise_for_status()
        fylker = resp.json()
        bounds: dict[str, tuple[str, tuple[float, float, float, float]]] = {}
        for f in fylker:
            nr = f["fylkesnummer"]
            name = f["fylkesnavn"]
            detail_resp = requests.get(f"{KOMMUNEINFO_API}/{nr}", timeout=10)
            detail_resp.raise_for_status()
            detail = detail_resp.json()
            coords = detail["avgrensningsboks"]["coordinates"][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            bounds[nr] = (name, (min(lats), min(lons), max(lats), max(lons)))
        _fylke_bounds_cache["data"] = bounds
        return bounds
    except (requests.exceptions.RequestException, KeyError, ValueError) as exc:
        print(f"Warning: Could not fetch fylke bounds from API ({exc}), using hardcoded fallback.")
        return FYLKE_BOUNDS


def _bbox_overlaps(bbox: BBox, bounds: tuple[float, float, float, float]) -> bool:
    """Check if user bbox overlaps with a fylke bounding box."""
    s, w, n, e = bounds
    return not (bbox.south > n or bbox.north < s or bbox.west > e or bbox.east < w)


def find_overlapping_fylker(bbox: BBox) -> list[tuple[str, str]]:
    """Return list of (code, name) for fylker that overlap the bbox."""
    results = []
    for code, (name, bounds) in get_fylke_bounds().items():
        if _bbox_overlaps(bbox, bounds):
            results.append((code, name))
    return results


def get_available_areas(metadata_uuid: str = N50_METADATA_UUID) -> list[dict]:
    """Fetch available download areas from Geonorge API."""
    url = f"{GEONORGE_API_BASE}/codelists/area/{metadata_uuid}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _find_area_entry(areas: list[dict], fylke_code: str) -> dict | None:
    """Find the area entry matching a fylke code."""
    for area in areas:
        if area.get("type") == "fylke" and area.get("code") == fylke_code:
            return area
    return None


def _format_available(area: dict, fmt: str, proj: str) -> bool:
    """Check if a given format+projection combination is available for an area."""
    for f in area.get("formats", []):
        if f.get("name") == fmt:
            for p in f.get("projections", []):
                if p.get("code") == proj:
                    return True
    return False


def place_order(
    fylke_code: str,
    fylke_name: str,
    metadata_uuid: str = N50_METADATA_UUID,
    fmt: str = TARGET_FORMAT,
    projection: str = TARGET_PROJECTION,
) -> OrderReceipt:
    """Place a download order via Geonorge API. Returns order receipt."""
    url = f"{GEONORGE_API_BASE}/order"
    order_payload = {
        "email": "",
        "orderLines": [
            {
                "metadataUuid": metadata_uuid,
                "areas": [
                    {
                        "code": fylke_code,
                        "type": "fylke",
                        "name": fylke_name,
                    }
                ],
                "projections": [
                    {
                        "code": projection,
                        "name": "EUREF89 UTM sone 33, 2d",
                        "codespace": f"http://www.opengis.net/def/crs/EPSG/0/{projection}",
                    }
                ],
                "formats": [{"name": fmt}],
            }
        ],
    }
    resp = requests.post(url, json=order_payload, timeout=60)
    resp.raise_for_status()
    return OrderReceipt.model_validate(resp.json())


def download_file(download_url: str, dest_path: Path) -> None:
    """Download a file with progress bar."""
    resp = requests.get(download_url, stream=True, timeout=300)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        open(dest_path, "wb") as f,
        tqdm(total=total, unit="B", unit_scale=True, desc=dest_path.name) as pbar,
    ):
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            pbar.update(len(chunk))


def extract_fgdb(zip_path: Path, dest_dir: Path) -> Path:
    """Extract a zip containing an FGDB and return the .gdb directory path."""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    # Find the .gdb directory inside
    for item in dest_dir.rglob("*.gdb"):
        if item.is_dir():
            return item
    msg = f"No .gdb directory found in {zip_path}"
    raise FileNotFoundError(msg)


def download_n50(bbox: BBox, data_dir: Path) -> list[Path]:
    """Download N50 FGDB files for all fylker overlapping the bbox.

    Returns list of paths to extracted .gdb directories.
    """
    n50_dir = data_dir / "n50"
    n50_dir.mkdir(parents=True, exist_ok=True)

    fylker = find_overlapping_fylker(bbox)
    if not fylker:
        print("Warning: No fylker found overlapping the given bounding box.")
        return []

    print(f"Bounding box overlaps {len(fylker)} fylke(r): {', '.join(n for _, n in fylker)}")

    # Fetch available areas from API
    areas = get_available_areas()

    gdb_paths: list[Path] = []
    for fylke_code, fylke_name in fylker:
        if existing := _find_existing(n50_dir, fylke_code, fylke_name):
            gdb_paths.append(existing)
            continue

        receipt = _order_fylke(fylke_code, fylke_name, areas)
        if receipt is None:
            continue

        for file_info in receipt.files:
            if gdb_path := _download_and_extract(n50_dir, file_info, fylke_code, fylke_name):
                gdb_paths.append(gdb_path)

    return gdb_paths


def _find_existing(n50_dir: Path, fylke_code: str, fylke_name: str) -> Path | None:
        """Return path to an already-extracted .gdb, or None."""
        existing = list(n50_dir.glob(f"*{fylke_code}*{fylke_name}*.gdb"))
        if existing:
            print(f"  Already downloaded: {existing[0].name}")
            return existing[0]
        return None


def _order_fylke(fylke_code: str, fylke_name: str, areas: list[dict]) -> OrderReceipt | None:
        """Validate availability and place order. Returns receipt or None on failure."""
        area_entry = _find_area_entry(areas, fylke_code)
        if area_entry is None:
            print(f"  Warning: Fylke {fylke_name} ({fylke_code}) not found in Geonorge areas")
            return None
        if not _format_available(area_entry, TARGET_FORMAT, TARGET_PROJECTION):
            print(f"  Warning: {TARGET_FORMAT}/{TARGET_PROJECTION} not available for {fylke_name}")
            return None

        try:
            print(f"  Ordering N50 for {fylke_name} ({fylke_code})...")
            return place_order(fylke_code, fylke_name)
        except requests.exceptions.RequestException as exc:
            print(f"  Warning: Failed to order N50 for {fylke_name} ({fylke_code}): {exc}")
            return None


def _download_and_extract(n50_dir: Path, file_info: OrderFile, fylke_code: str, fylke_name: str) -> Path | None:
    """Download a single file and extract its .gdb. Returns path or None on failure."""
    if file_info.status != "ReadyForDownload":
        print(f"    File not ready: {file_info.name}")
        return None

    download_url = file_info.downloadUrl
    filename = file_info.name or f"n50_{fylke_code}.zip"
    zip_path = n50_dir / filename

    if not zip_path.exists():
        print(f"    Downloading {filename}...")
        try:
            download_file(download_url, zip_path)
        except requests.exceptions.RequestException as exc:
            print(f"    Warning: Failed to download {filename}: {exc}")
            zip_path.unlink(missing_ok=True)
            return None
    else:
        print(f"    Already have {filename}")

    extract_dir = n50_dir / f"{fylke_code}_{fylke_name}"
    if not extract_dir.exists():
        print("    Extracting...")
        return extract_fgdb(zip_path, extract_dir)

    # Find existing gdb
    for gdb in extract_dir.rglob("*.gdb"):
        if gdb.is_dir():
            return gdb
    return None
