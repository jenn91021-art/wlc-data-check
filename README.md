# Seven checks before you trust a building register

**A small, readable data-quality kit for whole life carbon benchmarking.**

A benchmark is a ratio: kgCO₂e per m². The carbon side gets all the attention.
The m² side usually gets none - and it is the side that comes from a national
register, filled in by hundreds of people, exported from systems that disagree
with each other.

This repository takes a 200-building register, runs seven checks on it, and
measures what happens to the headline climate number if nobody does.

It is deliberately small: 206 rows, four short scripts, no dependencies beyond
`pandas`, `numpy` and `matplotlib`. It runs in about a second. Every line can be
read by a domain expert who has never written Python - which is the point.

---

## The result, up front

| | De-duplicated only | Checked and repaired | Error |
|---|---|---|---|
| Stock floor area | 586,806 m² | 389,581 m² | **+50.6%** |
| Stock energy intensity | 161.1 kWh/m²/yr | 145.0 kWh/m²/yr | **+11.1%** |

An analyst who remembers to remove duplicate rows - the one defect everybody
remembers - and stops there **overstates the floor area of this stock by half**.

That matters because every whole life carbon total scales linearly with floor
area. A 50% area error is a 50% error in total tonnes of CO₂e. The carbon
assessment can be perfect and the answer will still be wrong by half, because
the denominator was never checked.

![What the errors cost](figures/fig2_cost_of_not_checking.png)

---

## What is wrong with the register

![Seven checks](figures/fig1_whats_wrong.png)

**55 of 200 buildings (28%) fail at least one check.** The defects are the ones
that actually occur in national registers:

| Check | Caught | Why it matters |
|---|---|---|
| Floor area in ft² | 13 | Inflates area 10.8×, so intensity is understated 10.8× |
| Floor area missing | 12 | No - or a wrong - denominator; the record cannot be benchmarked |
| Year built missing | 9 | Removes the building from any vintage analysis |
| Floor area zero | 8 | An unknown treated as a number |
| EPC contradicts the meter | 7 | The label and the metered demand cannot both be right |
| Duplicate building ID | 6 | Totals are sums, so one repeated row adds real tonnes |
| EPC code invalid | 4 | Splits one band into several in any grouping |

---

## The seven checks, and why each one is defensible

The rule for this repository: **a check must have a reason rooted in building
physics or in how registers get filled in - never an arbitrary statistical
threshold.**

That distinction is the whole argument.

### 1 · The unit check is physical, not statistical

The tempting approach is "flag the top 1% of floor areas as outliers". It is
wrong in both directions: it flags genuinely large buildings, and it misses
medium-sized buildings recorded in square feet.

The alternative uses a fact about buildings:

> Floor area per storey has a ceiling by building type. A single dwelling
> reporting 1,200 m² on one storey is not a mansion - it is a square-foot
> figure in a square-metre column.

If dividing by 10.7639 brings the record back inside the ceiling, it was in
square feet. If it does not, the building is genuinely enormous and is left
alone. **On this register the check flagged 13 records and all 13 were confirmed
square feet - precision 1.000, and zero good records wrongly deleted.**

Why precision matters more than recall here: a false positive silently deletes a
real building, and nobody re-checks a record that has been quietly removed. A
miss at least leaves a visible outlier.

### 2 · The cross-field check needs domain knowledge

An EPC band implies a range of metered demand. A building certified **A** that
uses 350 kWh/m²/yr is not a data-entry typo you can catch with a regex - it is a
contradiction between two fields, and you can only see it if you know what a
certificate means.

This is the check that separates a building scientist from a generic data
analyst, and it is the one that found 7 records here. In real registers these
usually come from a retrofit that reached the certificate but never reached the
consumption record.

### 3 · Impossible values are voided, not clipped

Zero or negative floor area is not a small building, it is an unknown. Clipping
it to some minimum invents a number and hides the problem. Setting it to null
preserves the honesty and hands the decision to imputation.

### 4 · Duplicate keys keep the most complete record

`drop_duplicates(keep="first")` keeps whichever row happened to sort first -
exactly as likely to be the row with the blank floor area. We rank by how many
fields are filled and keep the best one.

### 5 · Labels are collapsed before anything is grouped

`  MFH `, `mfh` and `Mfh` are one building type. Left alone, a `groupby` reports
11 types instead of 4, each with a fraction of the data and a benchmark that
means nothing.

### 6 · Imputation is storey-scaled and flagged

Within a (type, country) group we take the **median area per storey**, then
multiply by that building's own storey count. A 3-storey house and a 1-storey
house should not receive the same imputed floor area.

Median, not mean, because floor area is right-skewed. Every imputed value is
flagged in a column, so any downstream result can be re-run without them.

### 7 · Order matters as much as the rules

The repair runs in a fixed sequence: de-duplicate → normalise labels → convert
units → void impossible → impute.

Get that order wrong and **nothing crashes** - you just get quietly wrong
answers. Imputing before voiding zeroes imputes from placeholders. Converting
units after computing a median uses the corrupt values in the reference. This is
the real difficulty of data cleaning, and it does not announce itself.

---

## Proof the repair did not damage anything

![Signal recovered](figures/fig3_signal_recovered.png)

The register was built so that **EPC band predicts metered demand** - that is
what a certificate is supposed to mean. After repair, median demand rises
monotonically across all seven bands, from 58 to 320 kWh/m²/yr.

This is a check on the *cleaning*, not on the data. A cleaning step that made
this relationship look better by changing the values would be a bug. A cleaning
step that destroyed it would mean records had been corrupted. Neither happened.

---

## Run it

```bash
git clone <your-repo-url>
cd wlc-data-check
pip install -r requirements.txt

python make_sample.py     # generate the register (or skip: it is committed)
python run_checks.py      # the data-quality report
python repair.py          # fix it in the right order, and show the cost
python figures.py         # the three figures
python -m pytest -q       # 10 tests
```

Under two seconds end to end.

### What you get

```
wlc-data-check/
├── make_sample.py          generate a 200-building register with known defects
├── checks.py               seven checks, one function each, plain-English reasons
├── run_checks.py           run every check, score it, write the report
├── repair.py               five repair steps in the only safe order
├── figures.py              three figures
├── test_checks.py          10 tests, one per behaviour claimed
├── requirements.txt
├── sample_buildings.csv    the messy input (206 rows)
├── buildings_clean.csv     the repaired register (200 rows)
├── data_quality_report.csv one row per check with counts and severity
├── flagged_records.csv     every failing row, with its rule and reason
└── figures/                three PNGs
```

---

## What this does not do

- **No carbon is calculated.** This is the denominator only. The numerator -
  EN 15978 A1–A5 and B6 - is a separate piece of work.
- **The register is synthetic.** 200 buildings from Austria, Hungary and Italy,
  built with a known signal and known defects so the checks can be scored. Real
  registers are worse in ways nobody has catalogued: geometry mismatches,
  address drift, retrofits recorded twice in different programme years.
- **The ceilings are heuristics.** 200 m²/storey for a dwelling is generous; a
  register containing a warehouse, a stadium or a car park would need them
  reviewed per country and per type.
- **Seven checks is not an exhaustive audit.** It is the seven that matter most
  for a carbon benchmark, chosen because each can be explained to a
  non-programmer in one sentence.

---

## Why this exists

The gap between a national building register and a trustworthy carbon benchmark
is not a modelling problem - the EN 15978 arithmetic is well understood. It is a
data problem: knowing which records you can defend, which you must exclude, and
what the exclusion costs you.

Written to make that step explicit and testable.

Requirements: `pandas`, `numpy`, `matplotlib` (+ `pytest` for the tests).
MIT licensed.
