
<h1 align="center">Noida Terrain-Depression Susceptibility</h1>  <p align="center">
  <em>An open, reproducible <strong>GIS + hydrology</strong> baseline for identifying where the terrain
  around Noida is most prone to collecting water — built terrain-first, evidence layer by layer,
  with every claim traceable to an artifact.</em>
</p>  <p align="center">
  <img alt="status" src="https://img.shields.io/badge/pipeline-V1→V7%20evidence%20complete-2ea44f">
  <img alt="crs" src="https://img.shields.io/badge/CRS-UTM%2044N%20(EPSG%3A32644)-blue">
  <img alt="dem" src="https://img.shields.io/badge/DEM-Copernicus%20GLO--30-informational">
  <img alt="python" src="https://img.shields.io/badge/Python-3.x-3776ab">
  <img alt="license" src="https://img.shields.io/badge/data-open%20sources-orange">
</p>  [IMPORTANT]</br>
**This project does NOT predict waterlogging.** It produces a terrain-depression
*susceptibility* map and then tests it, honestly, against rainfall, urban context, and
observed reports. The final result is a **well-founded, not-yet-validated hypothesis** —
and the project documents **exactly** where the evidence stops.




---

🎯 What this is (in one paragraph)

Noida's recurring monsoon waterlogging motivates the problem. Instead of shipping a black-box
"AI flood predictor," this is an independent, student-built, interpretable baseline: start
from elevation, find where terrain is prone to pond water, then add rainfall, urban context,
and observed-report layers one at a time — freezing and auditing each stage before the
next. Where data are missing, the gap is documented, never fabricated.

The headline scientific statement the evidence actually supports:

> "Using open DEM, reanalysis rainfall, and OpenStreetMap data, this project produces a
reproducible, internally-coherent map of where Noida's terrain is susceptible to water
collection. A coarse observed-corroboration test against the available waterlogging reports
returns insufficient — with only two verified parent observations the available overlap is
not enough to establish corroboration (the parent-matched null is already high at 90.5%, and
no statistical inference is claimed), neither validating nor refuting the map — and the
available data are also insufficient to validate it at the level of individual cells or to
establish a rainfall-timing link. The susceptibility map is therefore best described as a
well-founded, not-yet-validated hypothesis; the principal current validation gap is the
absence of public, spatially-precise observed-waterlogging data."



See outputs/v7ef_final_synthesis.md for the full verdict.


---

🧭 Pipeline at a glance

|Stage | Focus | Status	| Key output

| **V1** |	DEM → hydrology → TWI + depression depth | ✅	`depression_depth_utm.tif` |</br>
| **V2.1.1** |	Tiered terrain-depression candidates	| ❄️ `frozen	candidate_depressions.tif` |</br>
| **V3** |	Spatial / DEM-artifact-suspect diagnostics	| ✅	`artifact_suspect_report.txt` |</br>
| **V4** |	Depression × flow-accumulation cross-check	| ✅	`flow_crosscheck_report.txt` |</br>
| **V5** |	Rainfall integration (event-conditioned, ERA5)	| ✅	`fusion_v5_report.txt` |</br>
| **V6** |	Urban context (OSM buildings, roads, drainage)	| ✅	`urban_context_v6a_report.txt`, `drainage_proximity_v6b_report.txt` |</br>
| **V7** |	Validation vs observed reports + data-sufficiency verdict	| ✅	`v7ef_final_synthesis.md` |</br>


**❄️ frozen = specification locked; not modified by later stages. Every stage keeps V2.1.1 and
its predecessors untouched.**


---

## 🔬 The four evidence layers & what each established

### 1. Terrain (V1–V4) — the strongest layer

- Copernicus GLO-30 DEM (~30 m), analysed in UTM 44N. Deepest tier (>3 m) = 10,796 candidate cells.

- V3 flagged only 12.7% as DEM-artifact-suspect (87.3% unflagged).

- V4 cross-checked depression depth against D8 flow accumulation. Most deep cells (57.5%)
sit in the lowest flow band — consistent with genuine closed depressions (which pond
rather than drain). The two diagnostics are complementary, not statistically independent
(both from the same DEM).

- **Bucket-2 = 8,026 cells (6.783 km²)** = unflagged + low-flow → the most plausible closed
depressions, and the focus of every later layer.


### 2. Rainfall (V5) — coarse forcing, honest negative finding

- Open-Meteo **ERA5** reanalysis (~25 km, hourly), 2015–2023 Jun–Sep, audited clean.

- A frozen event-selection rule (no post-hoc tuning) picked a **Top-10 event catalogue**.

- **Key finding — anti-co-location:** the largest terrain-susceptible zone (SW, 4.29 km²,
63% of bucket-2) is **NOT** where the strongest coarse rainfall landed. Terrain-susceptibility
and strongest coarse forcing are **mildly anti-correlated** in space. (Coarse ~25 km scale;
not a 30 m attribution.)


### 3. Urban context (V6) — spatial characterisation only

- **Built:** susceptible depressions are **mostly non-built-up** (bucket-2 mean building
coverage 6.7%, only 17.9% of area has any building; SW zone even less at 14.4%).

- **Drainage:** susceptible depressions are generally **far from OSM-mapped drainage**
(median 767 m; 84.7% >250 m). **Caveat:** this reflects OSM mapped-network **sparsity**
(379 mapped drains, likely incomplete), **NOT** demonstrated drainage absence on the ground.


### 4. Observed corroboration (V7) — honestly reports "insufficient"

- **V7-A:** 8 reports → **6 usable**, only **2 with independent source verification**
(source re-verified, not the physical flood location ground-truthed). No public point-level
dataset was found; reports are sector/landmark scale, coarser than the 30 m grid.

- **V7-B:** primary unit = parent observation (**n = 2** verified). Both verified parents have
≥1 uncertainty-zone instance touching a susceptible cell (2/2, descriptive) — but a
**parent-matched null** already does so **90.5%** of the time (P(null ≥ observed) = 0.810),
so the observed overlap does not provide sufficient evidence for corroboration — and at
n = 2 no statistical inference is claimed. Instance-level 5/10 = 50% is a descriptive
diagnostic only (instances are subdivisions of the same 2 parents). Across the 20 geometry
instances, coordinates are mixed (7 web-verified / 13 approximate) → V7-B remains
provisional. **Verdict: insufficient to establish corroboration; neither validates nor refutes**.

- **V7-D:** **0/6** observations fall in a V5 Top-10 rainfall window — but 4/6 are outside the
ERA5 coverage period, so *"no temporal overlap" is **not** evidence against a rainfall trigger*.



---

## ✅ What is supported / ❌ what is not

| ✅ Supported	| ❌ Not supported |</br>

| A geometrically coherent terrain-susceptibility map with consistent hydrological context	| Confirmed waterlogging at any specific cell |</br>
| A reproducible, audited, frozen multi-layer pipeline | Statistically significant validation (n = 2; parent-matched null already 90.5%) |</br>
| An observed-corroboration test that honestly returns "insufficient"	Temporal corroboration with rainfall (nor contradiction) |</br>
| Explicitly documented data gaps	| Any causal claim (drainage / built-up / rainfall driving floods) |</br>



---

## 🧱 Candidate tiers (V2.1.1)

| Depth band	| Tier	| Meaning |

| < 0.2 m |	| Background |	| below candidate threshold |</br>
| 0.2 – 0.5 m | 	| Minor candidate	| shallow terrain-depression signal |</br>
| 0.5 – 2.0 m	| High candidate	| stronger terrain-depression signal |</br>
| 2.0 – 3.0 m	| Deep transition	| deeper terrain-depression signal |</br>
| > 3.0 m	| Deep terrain-depression	deep terrain feature (not assumed to be a channel)</br>


*"High candidate" = a depression-depth tier only. It does **not** mean high probability of
observed waterlogging.*

**V2.1.1 tier counts** (514,407 valid cells, ≥0.2 m threshold): Minor 35,751 (30.21 km²) ·
High 82,147 (69.43 km²) · Deep transition 15,332 (12.96 km²) · Deep >3 m 10,796 (9.12 km²).


---

## 🛰️ Method & spatial referencing

- **Single analysis CRS = UTM 44N.** All hydrology/terrain steps run in the projected metric
CRS; the tiering step hard-fails if its input isn't EPSG:32644.

- **WGS84 only for display.** Only the visualization layer is reprojected to EPSG:4326.

- **Explicit NoData.** −9999 (GDAL/QGIS-safe) with a validity mask excluding non-finite,
NoData, and physically-impossible negative depths.

- **Audit-first discipline.** Every stage has a dedicated audit/consistency script; the V6
consistency audit confirms all layers are bit-identical on the shared grid.

- **No fabricated data.** Missing rainfall/drainage/observed values stay missing.



---

## 🗂️ Repository structure

```text
noida-terrain-depression-susceptibility/
├── src/
│   ├── noida_waterlogging_v1.py        # V1 hydrology (flow accumulation, TWI)
│   ├── noida_waterlogging_v2.py        # V2 depression depth
│   ├── tier_map.py                     # V2.1.1 frozen tiered susceptibility map
│   ├── validate_artifacts.py           # V3 DEM-artifact-suspect diagnostics
│   ├── compute_flow.py                 # V4 D8 flow accumulation
│   ├── flow_crosscheck.py              # V4 depression x flow cross-check
│   ├── select_rainfall_events.py       # V5 frozen event-selection rule
│   ├── percell_event_metrics.py        # V5 per-cell rainfall metrics
│   ├── fusion_v5.py                    # V5 terrain x rainfall fusion
│   ├── audit_osm.py                    # V6 OSM data audit
│   ├── urban_context_v6a.py            # V6-A built-up context
│   ├── drainage_proximity_v6b.py       # V6-B drainage proximity
│   ├── consistency_audit_v6.py         # V6 cross-layer consistency audit
│   ├── observed_provenance_audit_v7a.py # V7-A observation provenance
│   ├── v7b_coarse_corroboration.py     # V7-B spatial corroboration + null model
│   └── v7d_temporal_match.py           # V7-D temporal match
│
├── outputs/
│   ├── candidate_depressions.tif       # V2.1.1 tier-coded raster (UTM 44N)
│   ├── flow_crosscheck_evidence.tif    # V4 evidence buckets
│   ├── selected_rainfall_events.json   # V5 frozen Top-10 event catalogue
│   ├── observed_waterlogging_provenance.csv # V7-A provenance table
│   ├── v7b_geometry.csv                # V7-B observation geometry
│   ├── v7b_corroboration_report.json   # V7-B result + null model
│   ├── v7b_corroboration_report.txt
│   ├── v7d_temporal_match_report.txt   # V7-D temporal match
│   └── v7ef_final_synthesis.md         # final evidence synthesis & verdict
│
├── data/                               # DEM input (not tracked)
├── README.md
└── LICENSE
```

## ⚙️ Setup & run

```bash
python3 -m venv venv
source venv/bin/activate
pip install pysheds rasterio folium matplotlib numpy branca geopandas osmnx shapely pyproj

# 1) Download Copernicus GLO-30 DEM for Noida from OpenTopography (GeoTIFF)
#    bbox ~ 77.23-77.43 E, 28.48-28.68 N  ->  place at data/noida_dem.tif
# 2) V1 hydrology -> TWI + depression depth
python3 src/noida_waterlogging_v2.py
# 3) V2.1.1 tiered susceptibility map (FROZEN)
python3 src/tier_map.py
# 4) V3->V7 evidence layers (each reads the frozen upstream outputs)
python3 src/validate_artifacts.py
python3 src/compute_flow.py && python3 src/flow_crosscheck.py
python3 src/select_rainfall_events.py && python3 src/percell_event_metrics.py && python3 src/fusion_v5.py
python3 src/audit_osm.py && python3 src/urban_context_v6a.py && python3 src/drainage_proximity_v6b.py
python3 src/observed_provenance_audit_v7a.py && python3 src/v7b_coarse_corroboration.py && python3 src/v7d_temporal_match.py
```

Note: V5 rainfall and V6 OSM steps require network access (Open-Meteo / Overpass APIs).</br>

**⚠️ Scientific limitations**
- Terrain depression is a **susceptibility indicator**, not evidence of observed waterlogging.
- At ~30 m resolution, street-level detail is not captured — results are **city-level**.
- ERA5 rainfall is **~25 km** coarse — it establishes temporal forcing plausibility, not
per-depression attribution.
- OSM drainage is a **partial mapped network —** proximity ≠ real drainage availability.
- Observed reports are **sector/landmark scale** and mostly **2024–2025**, outside the ERA5
window — so cell-level and temporal validation are **not yet possible**.
- **No suitable public point-level observed-waterlogging dataset was identified for this study —**
the single biggest barrier to full validation, and itself a finding about Indian urban
flood-data availability.

## 🤖 Where ML would (and would not) fit
ML was **deliberately not applied**: supervised flood-classification needs cell-level labels
that don't exist. If a spatially-precise, timestamped observed-waterlogging dataset becomes
available, the frozen V1–V6 layers could provide **candidate predictor features** and V7's
provenance framework could inform a reproducible labelling/validation protocol — but that
still needs feature engineering, spatial/temporal splits, leakage control, and imbalance
handling. Until then, documenting the gap is the honest stopping point. **Honesty over hype**.

## 🧰 Tech stack
Python · pysheds · rasterio · GeoPandas · Shapely · OSMnx · NumPy · Matplotlib · Folium ·
pyproj · Copernicus GLO-30 · ERA5 (Open-Meteo) · OpenStreetMap · UTM 44N

## 📊 Data sources
- **Elevation:** Copernicus GLO-30 DEM via OpenTopography</br>
- **Rainfall:** ERA5 reanalysis via Open-Meteo Historical API</br>
- **Urban features:** OpenStreetMap via OSMnx / Overpass</br>
- O**bserved reports:** public news & official reports (provenance-tracked in V7-A)</br>
*Built independently as an open, interpretable urban-hydrology baseline. Not affiliated with
any authority. Every quantitative claim in the final synthesis is traceable to a committed
artifact.*
