"""
test_checks.py — eight tests, one per behaviour the project claims.

You do not need to understand Python to read these. Each test builds a tiny
table by hand, runs one check on it, and asserts what should happen. If a test
fails, the project's claim is false and the README is lying.

Run:  python -m pytest -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from checks import (
    check_duplicates,
    check_epc_code,
    check_epc_consistency,
    check_missing_gfa,
    check_units,
    check_zero_gfa,
)
from repair import convert_units, impute, normalise_labels, remove_duplicates


def frame(**cols) -> pd.DataFrame:
    """Build a tiny table from column lists."""
    return pd.DataFrame(cols)


# ---------------------------------------------------------------------------
def test_duplicates_are_caught():
    df = frame(building_id=["B1", "B1", "B2"])
    assert len(check_duplicates(df)) == 1


def test_duplicates_keep_the_complete_row():
    # The second B1 has the floor area; keep="first" would have thrown it away.
    df = frame(
        building_id=["B1", "B1"],
        gfa_m2=[np.nan, 120.0],
        type=["sfh", "sfh"],
        country=["AT", "AT"],
    )
    out = remove_duplicates(df)
    assert len(out) == 1
    assert out["gfa_m2"].iloc[0] == 120.0


# ---------------------------------------------------------------------------
def test_missing_floor_area_is_caught():
    df = frame(building_id=["B1", "B2"], gfa_m2=[np.nan, 100.0])
    assert len(check_missing_gfa(df)) == 1


def test_zero_floor_area_is_caught_and_not_clipped():
    df = frame(building_id=["B1", "B2"], gfa_m2=[0.0, -5.0], type=["sfh", "sfh"],
               storeys=[1, 1])
    assert len(check_zero_gfa(df)) == 2


# ---------------------------------------------------------------------------
def test_square_feet_are_caught_by_the_physical_rule():
    # 2,000 ft2 is a normal house (186 m2). Typed as "2000" in the m2 column,
    # it is 1,000 m2 per storey for a 2-storey dwelling: impossible.
    df = frame(
        building_id=["B1", "B2"],
        type=["sfh", "sfh"],
        storeys=[2, 2],
        gfa_m2=[2000.0, 150.0],
    )
    caught = check_units(df)
    assert len(caught) == 1
    assert caught["building_id"].iloc[0] == "B1"


def test_legitimate_large_building_is_not_flagged():
    # A 12-storey office at 1,900 m2 per storey is big but real.
    df = frame(
        building_id=["B1"],
        type=["office"],
        storeys=[12],
        gfa_m2=[1900.0 * 12],
    )
    assert len(check_units(df)) == 0


def test_conversion_only_happens_when_it_fixes_the_record():
    df = frame(
        building_id=["B1", "B2"],
        type=["sfh", "sfh"],
        storeys=[2, 2],
        gfa_m2=[2000.0, 150.0],
    )
    out = convert_units(normalise_labels(df))
    assert out.loc[0, "gfa_unit_converted"]      # 2000 -> 185.8, plausible
    assert not out.loc[1, "gfa_unit_converted"]  # 150 was fine all along
    assert out.loc[0, "gfa_m2"] == pytest.approx(2000 / 10.7639, rel=1e-3)


# ---------------------------------------------------------------------------
def test_epc_code_and_conflict_checks():
    df = frame(
        building_id=["B1", "B2", "B3"],
        epc_class=["B", "X", "A"],
        kwh_m2_year=[90, 150, 350],   # B3 is rated A but uses 350: impossible
    )
    assert len(check_epc_code(df)) == 1                  # only 'X'
    conflict = check_epc_consistency(df)
    assert list(conflict["building_id"]) == ["B3"]


# ---------------------------------------------------------------------------
def test_imputation_scales_with_storeys():
    # Same type and country, different storeys. A flat group median would give
    # both 100 m2; the per-storey method should give 100 and 300.
    df = frame(
        building_id=["B1", "B2", "B3", "B4"],
        type=["sfh"] * 4,
        country=["AT"] * 4,
        storeys=[1, 1, 1, 3],
        gfa_m2=[100.0, 100.0, np.nan, np.nan],
        year_built=[1950.0, 1960.0, np.nan, 1970.0],
        kwh_m2_year=[100.0] * 4,
    )
    out = impute(df)
    assert out.loc[2, "gfa_m2"] == pytest.approx(100.0)   # 1 storey
    assert out.loc[3, "gfa_m2"] == pytest.approx(300.0)   # 3 storeys
    assert out["gfa_imputed"].sum() == 2   # B3 and B4 were both blank
    assert out["year_imputed"].sum() == 1


def test_labels_are_collapsed_and_invalid_epc_becomes_null():
    df = frame(
        building_id=["B1", "B2", "B3"],
        type=["SFH", " sfh ", "Mfh"],
        epc_class=["B", "epc_b", "X"],
        country=["at", "AT ", "At"],
        structure=["Timber", "timber", "TIMBER"],
    )
    out = normalise_labels(df)
    assert out["type"].nunique() == 2
    assert out["country"].nunique() == 1
    assert pd.isna(out.loc[2, "epc_class"])   # 'X' is not a valid band


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
