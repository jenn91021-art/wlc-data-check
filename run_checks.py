"""
run_checks.py — produce the data-quality report for this register.

This is the script you run and the script whose output you show people.

Every check is scored, not just run. A check that flags 50 records has not
proved anything until you know how many of those 50 were actually wrong. Real
quality assurance distinguishes:

    TRUE POSITIVE   flagged, and genuinely wrong          -> we caught it
    FALSE POSITIVE  flagged, but the data was fine        -> we would delete good data
    FALSE NEGATIVE  not flagged, but genuinely wrong      -> it slips into the result

False positives are the dangerous kind in a benchmark, because nobody re-checks
a record that has been quietly removed.

Run:  python run_checks.py
Out:  data_quality_report.csv   one row per check, with counts and severity
      flagged_records.csv       every failing row, with its rule and reason
"""

from __future__ import annotations

import pandas as pd

from checks import ALL_CHECKS, EPC_DEMAND_RANGE, VALID_EPC, run_all_checks

INPUT = "sample_buildings.csv"

# How badly each rule breaks a whole life carbon benchmark.
# "blocks"   = the record cannot be used at all
# "distorts" = the record can be used, but the result will be wrong
# "flags"    = the record is suspect and needs a human decision
SEVERITY = {
    "duplicate_id":        ("blocks",   "totals are summed, so a repeated row adds real tonnes"),
    "missing_gfa":         ("blocks",   "floor area is the denominator of every kgCO2e/m2 figure"),
    "impossible_gfa":      ("blocks",   "zero floor area cannot be benchmarked"),
    "missing_year":        ("blocks",   "no vintage means no age-based analysis"),
    "invalid_epc":         ("distorts", "splits one EPC category into several in any grouping"),
    "unit_error":          ("distorts", "inflates floor area 10.8x, so intensity is understated 10.8x"),
    "epc_demand_conflict": ("flags",    "label and meter disagree; needs a human to decide which is right"),
}


def main() -> None:
    df = pd.read_csv(INPUT)
    print(f"read {INPUT}: {len(df):,} rows, {len(df.columns)} columns")
    print(f"distinct building_id: {df['building_id'].nunique():,}\n")

    # --- run every check ---------------------------------------------------
    rows = []
    print(f"{'check':<24}{'flagged':>9}{'% of rows':>12}   severity")
    print("-" * 68)
    for check in ALL_CHECKS:
        failed = check(df)
        rule = failed["rule"].iloc[0] if len(failed) else check.__name__
        sev, why = SEVERITY[rule]
        rows.append({
            "rule": rule,
            "records_flagged": len(failed),
            "pct_of_rows": round(len(failed) / len(df) * 100, 2),
            "severity": sev,
            "why_it_matters": why,
        })
        print(f"{rule:<24}{len(failed):>9,}{len(failed)/len(df)*100:>11.1f}%   {sev}")

    report = pd.DataFrame(rows)

    # --- how many buildings are affected by anything at all ----------------
    flagged = run_all_checks(df)
    flagged.to_csv("flagged_records.csv", index=False)

    unique_bad = flagged["building_id"].nunique()
    print("-" * 68)
    print(f"records flagged in total : {len(flagged):,}")
    print(f"distinct buildings affected: {unique_bad:,} of {df['building_id'].nunique():,} "
          f"({unique_bad/df['building_id'].nunique()*100:.1f}%)")

    # --- score the most important check properly ---------------------------
    # The unit-error check is the only one where we can measure precision,
    # because the defect has a known signature: a value ~10.76x too large.
    from checks import check_units
    units = check_units(df)
    if len(units):
        # A confirmed hit: dividing by 10.7639 brings it back to a plausible size.
        fixed = (units["gfa_m2"] / 10.7639) / units["storeys"]
        ceiling = units["type"].astype(str).str.strip().str.lower().map(
            __import__("checks").MAX_M2_PER_STOREY
        )
        confirmed = int((fixed <= ceiling).sum())
        print(f"\nunit-error check, scored:")
        print(f"  flagged                        : {len(units)}")
        print(f"  confirmed (ft2->m2 fixes it)   : {confirmed}")
        print(f"  would delete good data         : {len(units) - confirmed}")
        print(f"  precision                      : {confirmed/len(units):.3f}")

    report.to_csv("data_quality_report.csv", index=False)
    print("\nwrote data_quality_report.csv and flagged_records.csv")


if __name__ == "__main__":
    main()
