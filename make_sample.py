"""
make_sample.py — create a small, realistic and deliberately messy building register.

This is NOT a national register. It is 200 buildings from three countries
(AT, HU, IT), sized so that the whole file opens in Excel and every line of the
analysis can be read by eye. A real register has 200,000 rows; the mess is the
same, only longer.

The data contains a REAL signal on purpose:

    age  ->  EPC band  ->  metered heating demand

So the checks in check_data.py are not decoration — they either find that signal
or break it. If the data had no signal, no cleaning quality would matter.

Run:  python make_sample.py
Out:  sample_buildings.csv   (206 rows: 200 buildings + 6 duplicates)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N = 200
SEED = 11

# building type -> (footprint m2 per storey, storeys, share of the stock)
TYPES = {
    "sfh":    ((60, 160),   (1, 3),  0.55),
    "mfh":    ((200, 800),  (2, 8),  0.28),
    "office": ((500, 2000), (3, 12), 0.10),
    "school": ((400, 1500), (2, 5),  0.07),
}

# EPC band -> typical metered demand, kWh/m2/yr (the physics the data must show)
BAND_DEMAND = {"A": 55, "B": 85, "C": 120, "D": 165, "E": 215, "F": 280, "G": 350}
TYPE_FACTOR = {"sfh": 1.0, "mfh": 0.9, "office": 1.15, "school": 0.85}

FT2_PER_M2 = 10.7639


def build_clean(rng: np.random.Generator) -> pd.DataFrame:
    """A clean, physically consistent register: no defects yet."""
    types = rng.choice(list(TYPES), size=N, p=[v[2] for v in TYPES.values()])
    rows = []
    for i, t in enumerate(types):
        (f_lo, f_hi), (s_lo, s_hi), _ = TYPES[t]
        storeys = int(rng.integers(s_lo, s_hi + 1))
        rows.append({
            "building_id": f"B{i:05d}",
            "country": rng.choice(["AT", "HU", "IT"]),
            "type": t,
            "year_built": int(rng.integers(1900, 2025)),
            "gfa_m2": round(float(rng.uniform(f_lo, f_hi)) * storeys, 1),
            "storeys": storeys,
            "structure": rng.choice(
                ["timber", "concrete", "masonry", "steel"], p=[0.12, 0.36, 0.40, 0.12]
            ),
            "epc_class": None,
            "kwh_m2_year": None,
        })
    df = pd.DataFrame(rows)

    # Age -> EPC band. Old buildings get worse labels, as in every real register.
    age = 2025 - df["year_built"]
    score = np.clip(age / 11.0 + rng.normal(0, 1.7, len(df)), 0, None)
    grades = np.array(list("ABCDEFG"))
    df["epc_class"] = grades[np.clip((score // 2).astype(int), 0, 6)]

    # Band + type -> metered demand. This is the signal the checks must protect.
    demand = (
        df["epc_class"].map(BAND_DEMAND).astype(float)
        * df["type"].map(TYPE_FACTOR).astype(float)
        * rng.normal(1.0, 0.12, len(df))
    )
    df["kwh_m2_year"] = np.round(demand.clip(25, 500), 1)
    return df


def inject_defects(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Add the six defect types that real national registers actually have."""
    df = df.copy()
    n = len(df)

    # 1. A few buildings whose EPC label contradicts their own metered demand.
    #    Physically impossible pairs: a G-rated building using 50 kWh, or an
    #    A-rated building using 300. Real registers contain these, usually from
    #    a retrofit that was recorded in the certificate but not in the meter.
    bad = rng.choice(n, 5, replace=False)
    for i in bad:
        df.at[i, "epc_class"] = "A" if df.at[i, "epc_class"] in "FGE" else "G"

    # 2. Missing floor area (8% of records).
    df.loc[rng.choice(n, 12, replace=False), "gfa_m2"] = np.nan

    # 3. Impossible zero floor area (4%).
    df.loc[rng.choice(n, 8, replace=False), "gfa_m2"] = 0.0

    # 4. Square feet typed into a column labelled m2 (7%).
    unit = rng.choice(n, 14, replace=False)
    df.loc[unit, "gfa_m2"] = (df.loc[unit, "gfa_m2"] * FT2_PER_M2).round(1)

    # 5. Missing construction year (4.5%).
    df.loc[rng.choice(n, 9, replace=False), "year_built"] = np.nan

    # 6. Inconsistent category labels: casing, stray spaces, invalid EPC codes.
    for col in ["type", "structure", "epc_class"]:
        idx = rng.choice(n, 10, replace=False)
        df.loc[idx, col] = [
            str(v).upper() if rng.random() < 0.5 else f" {v} "
            for v in df.loc[idx, col]
        ]
    df.loc[rng.choice(n, 4, replace=False), "epc_class"] = "X"   # invalid code

    # 7. Duplicate records (3%), reusing an existing building_id.
    dups = df.iloc[rng.choice(n, 6, replace=False)].copy()
    df = pd.concat([df, dups], ignore_index=True)

    # Shuffle so duplicates are not conveniently adjacent.
    return df.sample(frac=1, random_state=3).reset_index(drop=True)


def main() -> None:
    rng = np.random.default_rng(SEED)
    clean = build_clean(rng)
    dirty = inject_defects(clean, rng)
    dirty.to_csv("sample_buildings.csv", index=False)

    print(f"wrote sample_buildings.csv — {len(dirty)} rows, {len(dirty.columns)} columns")
    print(f"  {len(clean)} real buildings + {len(dirty) - len(clean)} duplicate records")
    print("  defects injected: ft2 units, missing GFA, zero GFA, missing year,")
    print("                    label casing, invalid EPC code, EPC-demand conflicts")


if __name__ == "__main__":
    main()
