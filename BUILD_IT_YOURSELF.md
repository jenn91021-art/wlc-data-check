# Build this yourself, step by step

*For someone who has never written Python. Nothing is assumed.*

---

## Part 1 — What are we building, and why would anyone care?

### The one-sentence version

> We take a messy list of buildings, run seven checks to find what is wrong with
> it, fix what we can, and measure how wrong the answer would have been if we
> hadn't bothered.

That's it. That's the project.

### But why does that matter?

A whole life carbon assessment produces one headline number:

```
embodied carbon + operational carbon  =  total kgCO2e
```

Then we divide it by the floor area to compare buildings fairly:

```
kgCO2e per m²     ← this is a "benchmark"
```

Think about that fraction. **The top of the fraction is the carbon. The bottom
is the floor area.** People spend years learning to calculate the top properly —
materials, EPDs, life cycle modules A1 to A5, B6, the lot.

Almost nobody checks the bottom.

But the floor area comes from a **national building register**: a giant
spreadsheet filled in by hundreds of different people, in different years, using
different software, typing in different languages. It has square feet in
columns labelled square metres. It has buildings listed twice. It has floor
areas of zero.

And here's the thing that makes this project interesting:

> **If the floor area is 50% too high, then your carbon benchmark is 50% too low.
> The carbon assessment can be completely perfect and the answer is still wrong
> by half — because the number you divided by was never checked.**

### The result we get

| | Analyst who only removes duplicate rows | Analyst who runs the checks | Error |
|---|---|---|---|
| Total floor area | 586,806 m² | 389,581 m² | **+50.6%** |
| Energy intensity | 161.1 kWh/m²/yr | 145.0 kWh/m²/yr | **+11.1%** |

An analyst who remembers the *one* defect everybody remembers — duplicates — and
stops there **overstates the floor area of this stock by half**.

That's the whole project on one line. Everything else is machinery to prove it.

### Why this is exactly what RISE needs

RISE co-leads **INDICATE**, which helps national teams in Ireland, Spain,
Czechia, Austria, Croatia, Hungary, Italy and Luxembourg produce building LCA
data. Their job is to define what data a country needs. That means deciding
which building records are *trustworthy enough to benchmark*.

You cannot do that job without data-quality judgement. This project is you
demonstrating that judgement, with numbers.

---

## Part 2 — The mental model before you touch code

### What is Python, actually?

A way of writing instructions to a computer. You write them in a text file, then
run the file. That's the whole relationship.

```
you write checks.py  →  you type "python checks.py"  →  computer does it
```

### What is pandas?

`pandas` is a toolbox for tables. If you can use Excel, you understand pandas
already — you just don't know the words yet:

| Excel | pandas |
|---|---|
| The spreadsheet | a **DataFrame** (`df`) |
| A column | a **Series** |
| A cell | a value at `df.loc[row, "column"]` |
| `FILTER` | a **boolean mask** — `df[df["gfa_m2"] > 100]` |
| `COUNTIF` | `.sum()` on a mask |
| `VLOOKUP` | `.merge()` |
| `AVERAGEIFS` | `.groupby().mean()` |
| Pivot table | `.groupby()` + `.agg()` |
| Deleting duplicates | `.drop_duplicates()` |

**You already think in tables. You are not starting from zero.**

### The four files, and what each one does

Think of it as four jobs in a kitchen:

| File | The job | In words |
|---|---|---|
| `make_sample.py` | **Make the ingredients** | Generates a fake but realistic register with defects deliberately baked in |
| `checks.py` | **The inspection** | Seven separate tests. Each one asks "is anything in this column impossible?" |
| `run_checks.py` | **The report card** | Runs all seven tests, counts what each one caught, writes it to a file |
| `repair.py` | **The fix** | Repairs the data — but in a specific order, and measures what changed |
| `figures.py` | **The poster** | Turns the numbers into three pictures |

And `test_checks.py` is a **safety net**: ten little checks on the checks
themselves, so you can prove the code still works after you change something.

---

# Part 3 — Build it, step by step

Follow these in order. Do not skip ahead. Each step ends with **what you should
see** — if your output doesn't match, stop and fix it before moving on.

---

## Step 0 — Install Python (10 minutes, once)

**Do this:**

1. Go to [python.org/downloads](https://python.org/downloads) and install the
   latest Python. **On Windows, tick the box that says "Add Python to PATH"** —
   this is the single most common beginner mistake.
2. Open a terminal:
   - **Windows:** search "Command Prompt"
   - **Mac:** search "Terminal"
3. Type this and press Enter:

```bash
python --version
```

**You should see** something like `Python 3.13.2`. Any version 3.9 or above is
fine.

> **If you see an error:** on Mac try `python3 --version` instead. Wherever this
> guide says `python`, use whichever one worked.

---

## Step 1 — Make a folder and install the toolboxes (5 minutes)

**Do this:**

```bash
mkdir wlc-data-check
cd wlc-data-check
pip install pandas numpy matplotlib pytest
```

**You should see** a lot of text ending in `Successfully installed...`.

**Why these four?**

| Package | What it does |
|---|---|
| `pandas` | Tables |
| `numpy` | Numbers and maths |
| `matplotlib` | Draws the charts |
| `pytest` | Runs the safety-net tests |

> **If `pip` is not found**, try `python -m pip install pandas numpy matplotlib pytest`.

---

## Step 2 — Create the data generator (20 minutes)

Create a new file called **`make_sample.py`** and paste in the full code from the
workspace. Now let's understand what it does, because you'll be asked.

### The idea

You cannot audit a messy register unless you know what the *correct* answer was.
So we do it backwards:

```
1. Build a clean, physically sensible register     → we know the truth
2. Mess it up in specific, counted ways             → we know what we broke
3. Save the messy version                           → this is what we analyse
```

That way, when a check says "I found 13 unit errors", you can ask "were there
13?" — and the answer is recorded.

### The physics inside it

The register is not random. Two relationships are real:

**1. Older buildings get worse energy labels.**
A building from 1905 is very likely band E, F or G. A building from 2020 is
likely A or B. That is true in every European country.

**2. The label predicts the meter.**
An A-rated building uses roughly 55 kWh/m²/yr. A G-rated one uses roughly 350.
That is what an Energy Performance Certificate *means* — it is supposed to
predict consumption.

We build those two relationships in deliberately, because later they let us
check that our cleaning didn't destroy them. More on that in Step 6.

**3. Floor area is footprint × storeys.**
A house with a 100 m² footprint and 2 storeys has 200 m² of floor area. This
matters enormously for the unit check — a record is only *impossible* if you know
how many storeys it has.

### The six defects we inject

| Defect | What we do | Why it's realistic |
|---|---|---|
| ft² in an m² column | multiply 14 values by 10.7639 | someone exported from an imperial system |
| Missing floor area | blank 12 values | incomplete survey |
| Zero floor area | set 8 values to 0 | placeholder left by an export script |
| Missing year | blank 9 values | old records |
| Messy labels | upper-case / add spaces to 10 per column | three people typing three ways |
| Invalid EPC | set 4 values to "X" | a coding error |
| Duplicates | copy 6 rows and re-add them | the classic double-entry |
| EPC vs meter clash | flip 5 labels to contradict their own demand | a retrofit recorded in the certificate but not the meter |

### Run it

```bash
python make_sample.py
```

**You should see exactly this:**

```
wrote sample_buildings.csv — 206 rows, 9 columns
  200 real buildings + 6 duplicate records
  defects injected: ft2 units, missing GFA, zero GFA, missing year,
                    label casing, invalid EPC code, EPC-demand conflicts
```

**Open `sample_buildings.csv` in Excel.** This is important — do it. You'll see
it's only 206 rows. You can scroll it. Look for a blank floor area. Look for
`MFH` written as `  MFH `. That's the mess, in front of you.

> **What just happened:** you created a dataset. Not downloaded one — created
> one, with known properties, so that every later claim can be tested.

---

## Step 3 — Write the seven checks (45 minutes — the heart of the project)

Create **`checks.py`** and paste it in.

### The one rule that governs this whole file

> **Every check must have a reason rooted in building physics or in how
> registers get filled in. Never an arbitrary statistical threshold.**

This is the sentence you say in the interview. Here's why it matters, using the
most important check as the example.

### The unit check — the important one

**The lazy way:** "flag the largest 1% of floor areas as outliers."

**Why that's wrong, twice over:**
- It flags genuinely large buildings (an office tower is not an error)
- It *misses* medium-sized buildings recorded in square feet (a 200 m² house
  typed as 2,153 is big, but not in the top 1% of a mixed stock)

**The physical way:**

```
Floor area per storey has a ceiling by building type.

A single dwelling reporting 1,200 m² on ONE storey
is not a mansion. It is square feet in a square-metre column.
```

So the check does this:

```
1. For each building, divide floor area by number of storeys
2. Compare it to the ceiling for that building type
   (sfh: 200, mfh: 900, office: 2200, school: 1700 m² per storey)
3. If it's over the ceiling → impossible → flag it
```

And then, crucially, the *repair* only converts a record **if dividing by 10.7639
actually fixes it.** If it doesn't, the building is genuinely enormous and we
leave it alone.

**That distinction — a rule, not a guess — is what makes this defensible.**

### The cross-field check — the one that needs a building scientist

An EPC band implies a range of metered demand:

```python
EPC_DEMAND_RANGE = {
    "A": (20, 90),     # an A-rated building uses 20-90 kWh/m²/yr
    "B": (50, 130),
    ...
    "G": (240, 520),
}
```

If a building is certified **A** but its meter says **350**, those two facts
cannot both be true. That's a flag.

You cannot write this check without knowing what a certificate means. A generic
data analyst would never think of it. **A building scientist writes it
immediately.** This is the check that proves what you are.

### How every check is shaped

Each one is a small function with the same rhythm:

```python
def check_units(df):
    # 1. work out which rows are impossible
    mask = ...

    # 2. return just those rows, with a reason attached
    return _rows(df, mask, "unit_error", "floor area per storey exceeds...")
```

`mask` is just a column of True/False. This is the pandas idea worth
understanding properly:

```python
df["gfa_m2"] > 100        # → a column of True/False, one per row
df[df["gfa_m2"] > 100]    # → only the rows where it's True
```

That's it. **`df[something that's True or False]` gives you the matching rows.**
You now understand the main way pandas works.

### Run it on its own (nothing visible yet — it's a toolbox)

`checks.py` doesn't print anything. It just defines seven functions. That's
correct — a toolbox shouldn't do anything until you use it.

---

## Step 4 — Produce the report card (15 minutes)

Create **`run_checks.py`** and run it:

```bash
python run_checks.py
```

**You should see exactly this:**

```
read sample_buildings.csv: 206 rows, 9 columns
distinct building_id: 200

check                     flagged   % of rows   severity
--------------------------------------------------------------------
duplicate_id                    6        2.9%   blocks
missing_gfa                    12        5.8%   blocks
impossible_gfa                  8        3.9%   blocks
unit_error                     13        6.3%   distorts
missing_year                    9        4.4%   blocks
invalid_epc                     4        1.9%   distorts
epc_demand_conflict             7        3.4%   flags
--------------------------------------------------------------------
records flagged in total : 59
distinct buildings affected: 55 of 200 (27.5%)

unit-error check, scored:
  flagged                        : 13
  confirmed (ft2->m2 fixes it)   : 13
  would delete good data         : 0
  precision                      : 1.000
```

### Read that bottom block again

```
flagged              : 13
confirmed            : 13
would delete good data: 0
precision            : 1.000
```

**This is the most important number in the project.** It says: this check
flagged 13 records, all 13 really were square feet, and it deleted no good data.

Why does that matter more than catching a lot? Because a **false positive**
silently deletes a real building, and **nobody ever re-checks a record that has
been quietly removed.** A miss leaves a visible outlier you can still catch. A
false positive is invisible forever.

That is a genuinely sophisticated point and it came out of your own project.

### What is "severity"?

You classify each defect by how badly it breaks a benchmark:

| Severity | Meaning |
|---|---|
| **blocks** | The record cannot be used at all |
| **distorts** | The record can be used, but the result will be wrong |
| **flags** | The record is suspect and needs a human to decide |

That's a judgement call, which is exactly the kind of judgement INDICATE needs.

### Files you now have

- `data_quality_report.csv` — one row per check, with counts and severity
- `flagged_records.csv` — every failing row, with its rule and reason

**Open `flagged_records.csv`.** Every bad row is listed with a plain-English
reason. That file is what you'd hand to a national statistics office.

---

## Step 5 — Repair it, in the only safe order (20 minutes)

Create **`repair.py`** and run it:

```bash
python repair.py
```

**You should see exactly this:**

```
repair log
  remove_duplicates       206 ->  200 rows   -6 duplicate keys
  normalise_labels                           type: 11 -> 4 categories, epc: 9 -> 7
  convert_units                              13 ft2 values converted
  void_impossible                            12 blank or impossible
  impute                                     20 floor areas and 9 years imputed

wrote buildings_clean.csv

effect on the headline stock figures
                                     naive    after repair     error
  stock floor area (m2)            586,806         389,581     50.6%
  stock intensity (kWh/m2)           161.1           145.0     11.1%

  Every figure of this kind scales linearly with floor area,
  so a 50% area error is a 50% error in total tonnes of carbon.
```

### Why the order matters — this is the subtle bit

The five repair steps run in a fixed sequence:

```
1. remove_duplicates     (before anything counts rows)
2. normalise_labels      (before any grouping or lookup)
3. convert_units         (before any statistic is computed)
4. void_impossible       (before imputation)
5. impute                (last — it needs a clean reference)
```

**Get this order wrong and nothing crashes.** You just get quietly wrong
answers:

- **Impute before voiding zeroes** → you impute *from* placeholder zeroes, so
  your "median" is dragged down by fake data
- **Convert units after computing a median** → your median is calculated from
  values that are 10x too large
- **Normalise labels after grouping** → `MFH` and `  MFH ` count as two types

**This is the real difficulty of data cleaning. It does not announce itself.**
There is no error message. There is just a wrong answer that looks fine.

That sentence, in an interview, tells them you've actually done this work rather
than read about it.

### The "naive" comparison

Look at the bottom block. `naive` means: **an analyst who removes duplicates and
stops.** That's the one defect everybody remembers.

```
naive total floor area  : 586,806 m²
repaired total          : 389,581 m²
overstatement           : +50.6%
```

You are not comparing yourself to doing nothing. You are comparing yourself to
**the competent-but-incomplete analyst** — and showing that even that person is
off by half. That's a much stronger and more honest claim.

### The imputation trick worth knowing

To fill a blank floor area, the obvious method is "use the median of buildings
of the same type and country". Fine — but it gives a 1-storey house and a
3-storey house the *same* floor area.

So we do better: we take the median **area per storey** for that group, then
multiply by *that building's own storey count*. The group supplies the typical
footprint; the row supplies the size.

Every imputed value gets a flag column (`gfa_imputed = True`), so anyone can
re-run the analysis without imputed rows. **Never hide an assumption — label
it.**

---

## Step 6 — Draw the three figures (15 minutes)

Create **`figures.py`** and run it:

```bash
python figures.py
```

**You should see:** `wrote 3 figures to figures/`

Open the three PNGs. Here's what each one argues.

### Figure 1 — What's wrong

A bar chart of all seven checks. Headline: **55 of 200 buildings (28%) fail at
least one check.**

Why it's built this way: it makes the mess *legible in three seconds*. Nobody
reads a table of defect counts. Everybody reads a bar chart.

### Figure 2 — What it costs *(the headline figure)*

Two bars: naive vs repaired, for floor area and for intensity.

**This is the figure you show people.** It answers the only question a
non-specialist asks: *"so what?"*

### Figure 3 — Proof you didn't break anything

This is the subtle one, and it's worth understanding because it's the mark of
someone who thinks like a scientist.

The register was built so that **EPC band predicts metered demand.** That's what
a certificate means. So after all our deleting, converting and imputing, we
check: *is that relationship still intact?*

It is. Median demand rises across all seven bands:

```
A: 58  →  B: 78  →  C: 113  →  D: 161  →  E: 211  →  F: 273  →  G: 320
```

Perfectly ordered. Nothing broken.

**Why this is a real check and not decoration:** if a cleaning step had made
that relationship look *better* by altering values, that would be a **bug** — you
never improve a correlation by cleaning, you only preserve or destroy it. This
figure proves the repair was conservative.

---

## Step 7 — Run the safety net (5 minutes)

```bash
python -m pytest -q
```

**You should see:**

```
..........                                                               [100%]
10 passed in 0.29s
```

Ten dots. Ten tests passed.

### What the tests actually do

Each test builds a tiny 2-row table by hand, runs one function on it, and
asserts what should happen. For example:

```python
def test_duplicates_keep_the_complete_row():
    # the second B1 has the floor area
    df = ...
    out = remove_duplicates(df)
    assert out["gfa_m2"].iloc[0] == 120.0    # we kept the useful one
```

You don't need to read Python to follow that. **If this test fails, the project's
claim is false and the README is lying.** That's what tests are for.

Proving your code works — rather than saying it does — is the difference between
a portfolio project and a professional one.

---

## Step 8 — Put it on GitHub (30 minutes)

### Create the repository

1. Go to [github.com](https://github.com) → sign up if needed
2. Click **+** (top right) → **New repository**
3. Name it `wlc-data-check`
4. Description: *A small data-quality kit for building registers — seven checks before you trust a carbon benchmark*
5. **Public**. Do not add a README (you have one).
6. Click **Create repository**

### Push your files

GitHub will show you commands. They are:

```bash
git init
git add .
git commit -m "Seven data-quality checks for building registers"
git branch -M main
git remote add origin https://github.com/YOURNAME/wlc-data-check.git
git push -u origin main
```

Replace `YOURNAME` with your GitHub username.

> **If `git` is not found**, install it from [git-scm.com](https://git-scm.com).

### Then do these three things

1. **Check the README renders** — open your repo page. The figures should
   display inline. If they're broken, the paths are wrong.
2. **Add topics** — click the gear next to "About" and add:
   `building-stock`, `data-quality`, `pandas`, `whole-life-carbon`, `lca`, `python`
3. **Copy your repo URL** — you need it for the CV.

### Your CV line

> **Data-Quality Checks for Building Registers** — open source, Python
> Seven checks over a 200-building register, with defects injected at known
> rates so the cleaning could be scored rather than asserted. An analyst who
> de-duplicates and stops overstates floor area by 50.6%; a physical floor-area-
> per-storey rule caught 13 unit errors with zero false positives. 10 tests.
> `github.com/YOURNAME/wlc-data-check`

---

# Part 4 — Understand it well enough to explain it

## The 40-second version (memorise this)

> "A whole life carbon benchmark is kgCO₂e per m². Everyone checks the carbon and
> nobody checks the m² — but the m² comes from a national register that's full of
> square feet and duplicates. I took a 200-building register, wrote seven checks,
> and measured what happens if you don't run them: an analyst who only removes
> duplicates overstates floor area by 50%, which means the carbon total is wrong
> by 50% too. The check I'm most pleased with is the unit check — instead of a
> statistical outlier threshold, it uses the fact that floor area per storey has
> a ceiling by building type, so a dwelling showing 1,200 m² per storey is square
> feet, not a mansion. That caught 13 records with zero false positives."

## Questions they will ask, and your answers

**"Why not just use a statistical outlier test?"**
> "Because it fails both ways. It flags genuinely large buildings, and it misses
> medium ones recorded in square feet. A physical ceiling flags exactly the
> impossible records. And false positives are worse than misses here — you never
> re-check a record you've quietly deleted."

**"Why median and not mean for imputation?"**
> "Floor area is right-skewed. A handful of very large buildings pulls a mean
> upwards, so you'd systematically overestimate the stock."

**"Isn't imputing 10% of the data dishonest?"**
> "It's dishonest if you hide it. Every imputed row is flagged, so anyone can
> re-run without them. For a benchmark, 20 rows out of 200 is acceptable; for a
> compliance decision it isn't."

**"What would you do with a real register?"**
> "The same seven checks, but I'd expect to add geometry checks — does the
> footprint match the shapefile — and duplicate detection that isn't based on
> the ID, because in real registers the same building arrives with two different
> IDs from two different programmes."

**"What did you get wrong?"**
> "My first version had 59 false positives on the unit check, because I'd
> generated floor area independently of storeys, so a normal 3,000 m² two-storey
> block looked impossible. I fixed the data generator to derive floor area as
> footprint × storeys, which is how buildings actually work. The lesson was that
> the check was only meaningful once the underlying model was physically
> consistent."

That last one is gold. **Every project has something you got wrong. Volunteering
it is the single strongest signal of a real practitioner.**

---

## Part 5 — Your build schedule

| Time | Do | Then check |
|---|---|---|
| 0:00–0:10 | Install Python, make folder, `pip install` | `python --version` works |
| 0:10–0:30 | Create `make_sample.py`, run it | 206 rows, 9 columns |
| 0:30–1:15 | Create `checks.py` (read it as you paste) | no output — that's correct |
| 1:15–1:30 | Create `run_checks.py`, run it | 55 of 200 buildings flagged |
| 1:30–1:50 | Create `repair.py`, run it | +50.6% overstatement |
| 1:50–2:05 | Create `figures.py`, run it | 3 PNGs |
| 2:05–2:10 | `pytest -q` | 10 passed |
| 2:10–2:40 | Push to GitHub | README renders with figures |
| 2:40–3:00 | Read Part 4 aloud twice | you can say the 40-second version |

**Total: about three hours, including installation.**

---

## The one habit that makes this yours

After it all works, change one thing:

```python
SEED = 11     # in make_sample.py — change to SEED = 42
```

Re-run everything. Different buildings, different defects, **same conclusions**.
That's what a seed is for: it proves your findings aren't an accident of one
particular dataset.

Then try changing a ceiling — set `"sfh": 120` instead of `200` and watch the
false positives appear in `run_checks.py`. You'll see *with your own eyes* why
the ceiling has to be set above the plausible maximum rather than at the
average.

**That is the moment the project becomes yours rather than something you
downloaded.** Do it before you push, and mention it in the interview.
