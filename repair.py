"""
repair.py — fix what the checks found, in the only order that is safe.

Order matters more than the code does:

    1. remove duplicate keys      before anything counts rows
    2. normalise labels           before any groupby or lookup
    3. convert units              before any statistic is computed
    4. void impossible values     before imputation, so they are not imputed from
    5. impute the remainder       last, because it needs a clean reference to
                                  compute a median from

Doing 3 before 2, or 5 before 4, gives quietly wrong answers rather than errors.
That is the whole difficulty of data cleaning: the wrong order does not crash.

Run:  python repair.py
Out:  buildings_clean.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from checks import MAX_M2_PER_STOREY, VALID_EPC

FT2_PER_M2 = 10.7639


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep one row per building_id — and keep the MOST COMPLETE one.

    The tempting one-liner is df.drop_duplicates("building_id", keep="first").
    That keeps whichever row happened to arrive first, which is exactly as
    likely to be the row with the blank floor area. So we rank by how many
    fields are filled and keep the best.
    """
    filled = df.notna().sum(axis=1)
    return (
        df.assign(_filled=filled)
          .sort_values(["building_id", "_filled"], ascending=[True, False])
          .drop_duplicates("building_id", keep="first")
          .drop(columns="_filled")
          .reset_index(drop=True)
    )


def normalise_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Force free-text categories onto a controlled vocabulary.

    '  MFH ' and 'mfh' and 'Mfh' are one building type. Left alone, a groupby
    reports three types, each with a fifth of the data and a meaningless
    benchmark.
    """
    df = df.copy()
    for col in ["country", "type", "structure", "heating_system", "epc_class"]:
        if col not in df.columns:
            continue
        s = (df[col].astype(str)
                   .str.strip()
                   .str.lower()
                   .str.replace(r"\s+", "_", regex=True))
        if col == "epc_class":
            s = s.str.replace(r"^epc_?", "", regex=True).str.upper()
            s = s.where(s.isin(VALID_EPC))       # invalid codes become NaN
        df[col] = s
    return df


def convert_units(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert square-foot records back to square metres.

    A record is converted ONLY if dividing by 10.7639 actually brings it inside
    the physical ceiling. Otherwise it is a genuinely large building and we
    leave it alone. This is the difference between a rule and a guess.
    """
    df = df.copy()
    ceiling = df["type"].map(MAX_M2_PER_STOREY)
    per_storey = df["gfa_m2"] / df["storeys"].replace(0, np.nan)
    suspect = df["gfa_m2"].notna() & ceiling.notna() & (per_storey > ceiling)

    converted = (df.loc[suspect, "gfa_m2"] / FT2_PER_M2).round(1)
    resolves = (converted / df.loc[suspect, "storeys"]) <= ceiling[suspect]

    df["gfa_unit_converted"] = False
    idx = converted.index[resolves]
    df.loc[idx, "gfa_m2"] = converted[resolves]
    df.loc[idx, "gfa_unit_converted"] = True
    return df


def void_impossible(df: pd.DataFrame) -> pd.DataFrame:
    """Zero or negative floor area is an unknown, not a small building."""
    df = df.copy()
    bad = df["gfa_m2"].notna() & (df["gfa_m2"] <= 0)
    df.loc[bad, "gfa_m2"] = np.nan
    return df


def impute(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill gaps with the median of the closest available group.

    We use the median, not the mean, because floor area is right-skewed: a few
    very large buildings would pull a mean upwards. We prefer the most specific
    group (type x country), then fall back to type, then to the whole stock.

    We never compute a group statistic from missing values, so the reference is
    always built from observed data only.

    Storey-scaled: within a group we take the median area PER STOREY, then
    multiply by that building's own storey count. A 3-storey house and a
    1-storey house should not get the same imputed area.
    """
    df = df.copy()
    observed = df[df["gfa_m2"].notna()]
    if observed.empty:
        raise ValueError("no observed floor areas — cannot impute")

    per_storey = observed["gfa_m2"] / observed["storeys"].replace(0, np.nan)
    ps_type_country = per_storey.groupby(
        [observed["type"], observed["country"]]
    ).median()
    ps_type = per_storey.groupby(observed["type"]).median()
    ps_all = per_storey.median()

    df["gfa_imputed"] = df["gfa_m2"].isna()

    for idx in df.index[df["gfa_m2"].isna()]:
        t, c, n = df.at[idx, "type"], df.at[idx, "country"], df.at[idx, "storeys"]
        ps = ps_type_country.get((t, c))
        if pd.isna(ps):
            ps = ps_type.get(t, ps_all)
        df.at[idx, "gfa_m2"] = round(float(ps) * float(n), 1) if pd.notna(n) else round(float(ps), 1)

    # Missing year: fill with the stock median so the row survives an age-based
    # analysis, and flag it so the assumption is visible.
    df["year_imputed"] = df["year_built"].isna()
    df["year_built"] = df["year_built"].fillna(round(df["year_built"].median()))

    return df


def repair(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Run the five steps in order and report what changed at each one."""
    n0 = len(df)

    def step(name: str, before: pd.DataFrame, after: pd.DataFrame, note: str):
        if verbose:
            print(f"  {name:<22} {len(before):>4} -> {len(after):>4} rows   {note}")

    if verbose:
        print("repair log")

    d = remove_duplicates(df)
    step("remove_duplicates", df, d, f"-{n0 - len(d)} duplicate keys")

    b = d
    d = normalise_labels(d)
    if verbose:
        print(f"  {'normalise_labels':<22} {'':>4}    {'':>4}        "
              f"type: {b['type'].nunique()} -> {d['type'].nunique()} categories, "
              f"epc: {b['epc_class'].nunique()} -> {d['epc_class'].nunique()}")

    d = convert_units(d)
    if verbose:
        print(f"  {'convert_units':<22} {'':>4}    {'':>4}        "
              f"{int(d['gfa_unit_converted'].sum())} ft2 values converted")

    b = d
    d = void_impossible(d)
    if verbose:
        print(f"  {'void_impossible':<22} {'':>4}    {'':>4}        "
              f"{int(b['gfa_m2'].isna().sum())} blank or impossible")

    d = impute(d)
    if verbose:
        print(f"  {'impute':<22} {'':>4}    {'':>4}        "
              f"{int(d['gfa_imputed'].sum())} floor areas and "
              f"{int(d['year_imputed'].sum())} years imputed")

    cols = ["building_id", "country", "type", "year_built", "gfa_m2", "storeys",
            "structure", "epc_class", "kwh_m2_year",
            "gfa_unit_converted", "gfa_imputed", "year_imputed"]
    return d[cols].reset_index(drop=True)


if __name__ == "__main__":
    raw = pd.read_csv("sample_buildings.csv")
    clean = repair(raw)
    clean.to_csv("buildings_clean.csv", index=False)
    print("\nwrote buildings_clean.csv")

    # --- what the defects would have done to the headline numbers ---------
    # A "naive" analyst removes duplicate keys -- the one defect everyone
    # remembers to handle -- and stops there. Everything else survives into the
    # result. This is the honest comparison, and it is the point of the project.
    naive = raw.drop_duplicates("building_id", keep="first")

    def stock_totals(d: pd.DataFrame) -> tuple[float, float]:
        gfa = float(d["gfa_m2"].sum())
        m = d["gfa_m2"].notna() & (d["gfa_m2"] > 0) & d["kwh_m2_year"].notna()
        w = d[m]
        intensity = float((w["kwh_m2_year"] * w["gfa_m2"]).sum() / w["gfa_m2"].sum())
        return gfa, intensity

    n_gfa, n_int = stock_totals(naive)
    c_gfa, c_int = stock_totals(clean)

    print("\neffect on the headline stock figures")
    print(f"  {'':<26}{'naive':>14}{'after repair':>16}{'error':>10}")
    print(f"  {'stock floor area (m2)':<26}{n_gfa:>14,.0f}{c_gfa:>16,.0f}"
          f"{(n_gfa - c_gfa) / c_gfa * 100:>9.1f}%")
    print(f"  {'stock intensity (kWh/m2)':<26}{n_int:>14.1f}{c_int:>16.1f}"
          f"{(n_int - c_int) / c_int * 100:>9.1f}%")
    print("\n  Every figure of this kind scales linearly with floor area,")
    print("  so a 50% area error is a 50% error in total tonnes of carbon.")
