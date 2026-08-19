# Noida Terrain-Depression Susceptibility — V7-E/F Final Synthesis & Data-Sufficiency Verdict

*Scope: this document synthesises the whole V1–V7 pipeline. It introduces NO new
computation and NO new statistics — every number below is quoted from an already-committed
artifact. Its only job is to state, honestly, exactly how strong a claim the accumulated
evidence supports.*

---

## V7-E — Evidence synthesis across the four layers

### 1. Terrain signal (V1–V4) — how strong is the depression susceptibility?

This is the **strongest, best-supported layer** of the project.

- V2.1.1 froze a tiered terrain-depression map from a Copernicus GLO-30 DEM (~29 m,
  UTM 44N). The deepest tier (>3 m) holds **10,796 candidate cells**.
- V3 artifact-diagnostics flagged only **1,371 (12.7%)** of those as DEM-artifact-suspect,
  leaving **9,425 (87.3%) unflagged** — i.e. the deep signal is mostly not obvious noise.
- V4 cross-checked depression depth against independent D8 flow accumulation. The deep
  tier's flow distribution is modestly elevated (tier-4 deep median accumulation = 7),
  but most deep cells (57.5%) sit in the lowest 'negligible' flow band — consistent with
  genuine *closed* depressions that accumulate little upslope flow, rather than a single
  flow-convergence story. The two diagnostics (depth and flow accumulation) are treated as
  separate, complementary evidence layers rather than as mutually confirming measurements
  (both are derived from the same DEM, so they are not statistically independent).
- V4 partitioned the deep cells into evidence buckets. **Bucket-2 = 8,026 cells
  (6.783 km²)**: unflagged + low-flow → the most plausible *closed* depressions, and the
  layer most relevant to urban ponding.

**What the terrain layer supports:** a geometrically coherent map of where Noida's terrain
is *prone to collect water*, with consistent hydrological context from the flow cross-check.
The low flow accumulation across most deep cells is itself consistent with closed
depressions (which pond rather than drain).
**What it does NOT support:** that any of these cells *has* flooded. Throughout, the framing
stayed "candidates, NOT confirmed waterlogging."

### 2. Rainfall signal (V5) — what does it establish, and what not?

- Source: Open-Meteo **ERA5** reanalysis (~25 km, hourly), 2015–2023 June–September,
  4 ERA5 cells over Noida, dataset audited clean (26,352 hrs/cell, 0 missing/neg/dup).
- A frozen, explicitly-defined event-selection rule (no post-hoc tuning) selected a
  **Top-10 event catalogue** from 710 raw spells, of which 110 met the qualification
  criteria. The separately-validated source-check date was NOT selected by the ranking
  rule — a useful check against outcome-driven event selection.
- V5 fusion with terrain produced the project's most important *negative* finding —
  **ANTI-CO-LOCATION**: the largest terrain-susceptible zone (SW cell 28.5,77.25 —
  4.29 km², 63% of bucket-2) is NOT where the strongest coarse rainfall forcing landed.
  The two strongest max-6h events (100.2 mm, 69.9 mm) both fell on cell 28.75,77.5, where
  susceptible area is only 0.10 km²; only the 4th- and 9th-ranked events co-located with
  the SW susceptible zone. Terrain-susceptibility and strongest coarse forcing are mildly
  anti-correlated in space.

**What the rainfall layer supports:** temporal *forcing plausibility* at a coarse ~25 km
scale, and an honest statement that terrain-susceptibility and strongest coarse forcing are
mildly anti-correlated in space.
**What it does NOT support:** any rainfall × depression = flood-risk score, or any 30 m
rainfall precision. ERA5's 25 km resolution is explicitly too coarse to attribute forcing
to individual depressions.

### 3. Urban context (V6) — what did drainage/built-up proximity add?

- **V6-A (built context):** terrain-susceptible depressions are **mostly non-built-up** —
  whole bucket-2 building coverage mean 6.7%, median 0%, only 17.9% of area has any
  building. The SW zone is even less urbanised (5.6% mean, 14.4% any-building). Densely
  built eastern quadrants hold little susceptible area (mild inverse pattern).
- **V6-B (drainage proximity):** susceptible depressions are generally **far from
  OSM-mapped drainage** — median nearest drain 767 m; 84.7% of cells >250 m from any mapped
  drain. **Critical caveat locked:** this reflects OSM mapped-network **sparsity** (379
  mapped drains for all Noida is likely incomplete and not equivalent to the full on-ground
  drainage network), NOT demonstrated drainage absence on the ground.

**What the urban layer supports:** a spatial characterisation — Noida's largest
terrain-susceptible zone is relatively undeveloped and poorly covered by *mapped* drainage.
**What it does NOT support:** any causal risk direction. "Undeveloped + susceptible" could
mean development-critical land OR naturally-draining farmland; the data cannot decide.
"Far from mapped drainage" is NOT "drainage crisis."

### 4. Observed corroboration (V7-A/B/D) — what do the reports support?

- **V7-A (provenance):** 8 observation records; **6 usable** (in-bbox, KEEP/KEEP-WITH-
  UNCERTAINTY), of which only **2 have independent source verification** in the current
  provenance record (traffic-police hotspots; a 2021 HT report) — i.e. the *source* was
  re-verified, NOT the physical flood location ground-truthed. No public point-level
  complaint database exists; sector precision is
  coarser than the 30 m grid. Terminology held: "observed reports," never "ground truth."
- **V7-B (coarse spatial corroboration):** using uncertainty zones (500–1000 m), observed
  locations overlap bucket-2 at **70%** (primary), vs a null model of random Noida points at
  **56.8%** → difference **+13.2 pts**, bootstrap **p = 0.291** (exploratory, n = 2 verified
  parents). Direction = positive relative to the null; magnitude = not statistically
  decisive. Coordinates are approx_unverified → **PROVISIONAL**.
- **V7-D (temporal):** **0/6** observations overlap a V5 Top-10 event window (exact, ±1 d,
  ±2 d). But 4/6 observations fall OUTSIDE the V5 2015–2023 Jun–Sep coverage, and the 2
  inside simply don't coincide with the *strongest-10* spells. Only 1/6 has a documented
  rainfall amount (26.5 mm, itself pending re-verification).

**What the observed layer supports:** a weak, directionally-consistent spatial signal —
reported waterlogging locations tend to fall near terrain-susceptible zones slightly more
than chance, but not enough to establish predictive validity.
**What it does NOT support:** cell-level validation, statistical significance, or temporal
corroboration. Crucially, **"no V5 temporal overlap" is NOT evidence against a rainfall
trigger** — it reflects a catalogue-vs-record coverage mismatch.

---

## V7-F — Final verdict & data-sufficiency conclusion

### What IS supported

1. **Terrain-depression susceptibility is geometrically coherent and has consistent
   hydrological context in the flow-accumulation cross-check.** The artifact-suspect
   fraction is low (12.7%), and the low flow accumulation across most deep cells is
   consistent with genuine closed depressions. This is a credible *susceptibility* map —
   the project's core deliverable.
2. **A reproducible, honestly-caveated multi-layer pipeline** (terrain → rainfall → urban →
   observed), every stage frozen, audited, and consistency-checked (V6 audit: all layers
   bit-identical on the shared grid).
3. **A weak, directionally-consistent spatial signal** from the available observed
   reports (70% vs 56.8% null) — but insufficient evidence to establish predictive
   validity (p = 0.291, n = 2 verified parent observations, approximate coordinates).

### What is NOT supported

1. **No confirmed waterlogging at any specific cell.** The map identifies *candidates*, never
   confirmed floods.
2. **No statistically significant validation** (p = 0.291, n = 2 verified observations,
   coarse uncertainty zones).
3. **No temporal corroboration** with the rainfall catalogue — and, symmetrically, **no
   temporal contradiction** either.
4. **No causal claims** about drainage, built-up land, or rainfall driving waterlogging.

### Data gaps (the honest limiting factors)

- **No suitable public point-level observed-waterlogging dataset was identified for this
  study** (coordinate + timestamp + depth). This is the single biggest blocker to
  quantitative validation — and is itself a finding about Indian urban flood-data
  availability.
- **Temporal coverage mismatch:** frozen rainfall catalogue 2015–2023 vs observation record
  mostly 2024–2025.
- **Spatial precision mismatch:** observations at sector/landmark scale (~500–1000 m) vs a
  30 m susceptibility grid; ERA5 rainfall at ~25 km.
- **OSM drainage network is likely incomplete** (379 mapped drains), so drainage-proximity
  cannot be read as real drainage availability.
- **Observation coordinates are approx_unverified**, so V7-B is provisional.

### Final scientific claim — exactly how strong

> **"Using open DEM, reanalysis rainfall, and OpenStreetMap data, this project produces a
> reproducible, internally-coherent map of where Noida's terrain is susceptible to water
> collection. The available observed-waterlogging reports show a weak directional spatial
> consistency with this map at a coarse, uncertainty-zone scale, but the available data are
> insufficient to validate it at the level of individual cells or to establish a
> rainfall-timing link. The susceptibility map is therefore best described as a well-founded,
> not-yet-validated hypothesis; the principal current validation gap is the absence of
> public, spatially-precise observed-waterlogging data — itself a documented gap."**

This is a **terrain-susceptibility screening layer with partial, directional observational
corroboration and an explicitly documented validation-data gap** — NOT a validated
flood-prediction model. Stated that way, every clause is backed by a committed artifact, and
nothing is overclaimed.

### Where ML would (and would not) fit

ML was correctly *not* applied: supervised flood-classification needs cell-level labels that
do not exist. If a spatially-precise, timestamped observed-waterlogging dataset becomes
available (e.g. an official complaint GIS export), the frozen V1–V6 layers could provide
candidate predictor features, while V7's provenance framework could inform a reproducible
labelling and validation protocol. That step would still require feature engineering,
spatial/temporal train-test splits, leakage control, and class-imbalance handling — none of
which the current data support. Until then, documenting the gap is the honest and correct
stopping point.
