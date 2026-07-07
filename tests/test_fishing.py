"""Tests for the fishing genera bitmask."""

import pandas as pd

from telttur.scoring.fishing import PRIZED_GENERA, _build_genera_mask


def _bit_of(genus: str) -> int:
    code = next(e["code"] for e in PRIZED_GENERA if e["genus"] == genus)
    assert isinstance(code, int)
    return code


def test_each_genus_sets_its_exported_bit() -> None:
    # The bit index in the mask must match the "code" exported to the frontend.
    for entry in PRIZED_GENERA:
        genus = str(entry["genus"])
        mask = _build_genera_mask(pd.Series([f"{genus} testus"]))
        assert mask == 1 << _bit_of(genus), f"bit mismatch for {genus}"


def test_multiple_genera_are_ored_together() -> None:
    names = pd.Series(["Salmo trutta", "Esox lucius", "Salmo salar"])
    assert _build_genera_mask(names) == (1 << _bit_of("Salmo")) | (1 << _bit_of("Esox"))


def test_unknown_genus_and_empty_names_give_zero() -> None:
    assert _build_genera_mask(pd.Series(["Rattus norvegicus", "", "Unknownus"])) == 0


def test_empty_series_gives_zero() -> None:
    assert _build_genera_mask(pd.Series([], dtype=str)) == 0
