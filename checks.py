"""
checks.py — seven small, readable data-quality checks.

Every check is one function. Each returns a DataFrame of the rows that FAIL,
with a `reason` column explaining why in plain words.

The design principle: a check must have a REASON rooted in building physics or
in how registers are actually filled in — not an arbitrary statistical
threshold. "Floor area is negative" is arbitrary to explain. "A single dwelling
cannot have 1,200 m2 on one storey" is something any building professional
immediately believes.

This file is deliberately boring. Short functions, obvious names, no clever
tricks. Anyone should be able to read it and say whether they agree.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Maximum credible floor area per storey, by building type (m2/storey).
# These are set ABOVE the plausible maximum, not at the average, so that a
# legitimate large building never trips the check.
MAX_M2_PER_STOREY = {"sfh": 200, "mfh": 900, "office": 2200, "school": 1700}

# EPC bands are a closed set. Anything else is a coding error in the register.
VALID_EPC = list("ABCDEFG")

# Typical metered demand for each band (kWh/m2/yr). Used to detect records whose
# label and meter disagree. Wide bands, because real buildings vary.
EPC_DEMAND_RANGE = {
    "A": (20, 90),
    "B": (50, 130),
    "C": (80, 180),
    "D": (110, 240),
    "E": (150, 300),
    "F": (190, 380),
    "G": (240, 520),
}


def _rows(df: pd.DataFrame, mask: pd.Series, rule: str, reason: str) -> pd.DataFrame:
    """Helper: return the failing rows with a rule name and a reason."""
    out = df.loc[mask].copy()
    out["rule"] = rule
    out["reason"] = reason
    return out


# ---------------------------------------------------------------------------
# 1. Duplicate records
# ---------------------------------------------------------------------------
def check_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    A building_id must appear once. Repeats inflate every total that follows,
    and because totals are sums, one duplicated row adds real tonnes.

    Note we check the KEY, not the whole row: duplicate keys are the dangerous
    case, because two rows then describe the same building twice.
    """
    mask = df["building_id"].duplicated(keep="first")
    return _rows(df, mask, "duplicate_id",
                 "building_id appears more than once")


# ---------------------------------------------------------------------------
# 2. Missing floor area
# ---------------------------------------------------------------------------
def check_missing_gfa(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gross floor area is the denominator of every intensity figure we report
    (kgCO2e/m2). Without it the record cannot enter a benchmark at all.
    """
    mask = df["gfa_m2"].isna()
    return _rows(df, mask, "missing_gfa", "floor area is blank")


# ---------------------------------------------------------------------------
# 3. Impossible floor area
# ---------------------------------------------------------------------------
def check_zero_gfa(df: pd.DataFrame) -> pd.DataFrame:
    """
    Zero or negative floor area is physically impossible for a building that
    exists. These are usually placeholder values left by an export script.
    We do NOT clip them to a small number: an unknown is not a small building.
    """
    mask = df["gfa_m2"].notna() & (df["gfa_m2"] <= 0)
    return _rows(df, mask, "impossible_gfa", "floor area is zero or negative")


# ---------------------------------------------------------------------------
# 4. Unit errors (square feet in a square metre column)
# ---------------------------------------------------------------------------
def check_units(df: pd.DataFrame) -> pd.DataFrame:
    """
    The physical test, and the most useful check in this file.

    Floor area per storey has a ceiling by building type. If a single dwelling
    reports 1,200 m2 on one storey, it is not a mansion — it is a square-foot
    figure in a square-metre column (1 ft2 = 0.0929 m2, so the number is about
    10.76x too large).

    Why this beats a statistical outlier test: a threshold like "flag the top 1%
    of floor areas" will flag genuinely large buildings and miss medium-sized
    ones recorded in ft2. A physical ceiling flags exactly the impossible
    records.
    """
    ceiling = df["type"].astype(str).str.strip().str.lower().map(MAX_M2_PER_STOREY)
    per_storey = df["gfa_m2"] / df["storeys"].replace(0, np.nan)
    mask = df["gfa_m2"].notna() & ceiling.notna() & (per_storey > ceiling)
    return _rows(df, mask, "unit_error",
                 "floor area per storey exceeds the physical ceiling for this "
                 "building type — likely square feet in a column labelled m2")


# ---------------------------------------------------------------------------
# 5. Missing construction year
# ---------------------------------------------------------------------------
def check_missing_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    Year built drives the vintage of the stock, which is the main explanatory
    variable for both embodied carbon and operational demand. A missing year
    removes a building from any analysis by age.
    """
    mask = df["year_built"].isna()
    return _rows(df, mask, "missing_year", "construction year is blank")


# ---------------------------------------------------------------------------
# 6. Invalid EPC code
# ---------------------------------------------------------------------------
def check_epc_code(df: pd.DataFrame) -> pd.DataFrame:
    """
    EPC bands are a closed set A-G. 'X', 'n/a', '' or 'EPC B' are coding errors.
    These matter because a groupby on a dirty EPC column silently creates extra
    categories, each with too few buildings to benchmark.
    """
    epc = df["epc_class"].astype(str).str.strip().str.upper()
    mask = ~epc.isin(VALID_EPC)
    return _rows(df, mask, "invalid_epc", "EPC class is not a letter A-G")


# ---------------------------------------------------------------------------
# 7. Label and meter disagree
# ---------------------------------------------------------------------------
def check_epc_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    The cross-field check, and the one that needs domain knowledge rather than
    code.

    An EPC band implies a range of metered demand. If a building is certified A
    but uses 350 kWh/m2/yr, the label and the meter cannot both be right. This
    is common in real registers: a retrofit is recorded in the certificate but
    never reaches the consumption record.

    This check cannot be automated without knowing what the bands mean — which
    is precisely the kind of check a building scientist should be writing.
    """
    epc = df["epc_class"].astype(str).str.strip().str.upper()
    low = epc.map(lambda b: EPC_DEMAND_RANGE.get(b, (np.nan, np.nan))[0])
    high = epc.map(lambda b: EPC_DEMAND_RANGE.get(b, (np.nan, np.nan))[1])
    kwh = df["kwh_m2_year"]
    mask = kwh.notna() & low.notna() & ((kwh < low) | (kwh > high))

    out = _rows(df, mask, "epc_demand_conflict",
                "metered demand is outside the range its EPC band allows")
    if len(out):
        out["expected_range"] = [
            f"{int(lo)}-{int(hi)} kWh/m2/yr"
            for lo, hi in zip(low[mask], high[mask])
        ]
    return out


# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------
ALL_CHECKS = [
    check_duplicates,
    check_missing_gfa,
    check_zero_gfa,
    check_units,
    check_missing_year,
    check_epc_code,
    check_epc_consistency,
]


def run_all_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Run every check and return one combined table of failing rows."""
    results = []
    for check in ALL_CHECKS:
        failed = check(df)
        if len(failed):
            results.append(failed)
    if not results:
        return pd.DataFrame()
    combined = pd.concat(results, ignore_index=True)
    cols = ["rule", "reason", "building_id"] + [
        c for c in combined.columns
        if c not in ("rule", "reason", "building_id")
    ]
    return combined[cols].sort_values(["rule", "building_id"]).reset_index(drop=True)
