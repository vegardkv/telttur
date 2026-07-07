"""Shared HTTP fetch helper with retry/backoff for raster tile downloads."""

from __future__ import annotations

import time

import requests

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4  # 1 initial + 3 retries


def fetch_with_retry(  # noqa: PLR0913
    url: str,
    params: dict[str, str],
    *,
    timeout_s: float,
    backoff_base_s: float,
    expected_content_types: tuple[str, ...],
    error_label: str,
) -> requests.Response:
    """GET *url*, retrying transient failures with exponential backoff.

    Retries HTTP 429/5xx, timeouts, and connection errors up to _MAX_ATTEMPTS
    total attempts, waiting ``backoff_base_s * 2**n`` seconds between tries.
    The response Content-Type must contain one of *expected_content_types*.
    Raises RuntimeError on any final failure (fail-fast policy, see CLAUDE.md).
    """
    resp = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout_s)
            resp.raise_for_status()
            break
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if attempt < _MAX_ATTEMPTS and status in _RETRY_STATUSES:
                _backoff(backoff_base_s, attempt, f"HTTP {status}")
            else:
                raise RuntimeError(f"Failed to fetch {error_label}: {exc}") from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt < _MAX_ATTEMPTS:
                _backoff(backoff_base_s, attempt, type(exc).__name__)
            else:
                raise RuntimeError(f"Failed to fetch {error_label}: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch {error_label}: {exc}") from exc

    assert resp is not None
    ct = resp.headers.get("Content-Type", "").lower()
    if not any(expected in ct for expected in expected_content_types):
        preview = resp.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"{error_label} returned unexpected Content-Type {ct!r}. Response: {preview}"
        )
    return resp


def _backoff(backoff_base_s: float, attempt: int, reason: str) -> None:
    wait = backoff_base_s * (2 ** (attempt - 1))
    print(f"      {reason}, retrying in {wait:.0f}s (attempt {attempt}/{_MAX_ATTEMPTS}) ...")
    time.sleep(wait)
