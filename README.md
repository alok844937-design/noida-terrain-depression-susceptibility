# Noida Terrain-Depression Susceptibility

An open, reproducible **GIS + hydrology** baseline for identifying where the terrain
around Noida is most prone to collecting water.

> **This project does NOT predict waterlogging.** It produces terrain-depression
> susceptibility *candidates* derived purely from elevation — candidate indicators of
> where water could accumulate, not confirmed waterlogging locations. Rainfall, drainage
> capacity, and infrastructure are layered in later (see Roadmap).

## Why this exists

Noida's recurring monsoon waterlogging motivates the broader problem this project
explores. This is an independent, student-built, open-source baseline: start from the
terrain, stay interpretable, and add evidence layer by layer — instead of over-claiming
with a black-box "AI flood predictor."

## What it does (current: V2.1.1)

1. Uses a Copernicus GLO-30 (~30 m) DEM for the Noida study area.
2. Reprojects the DEM to UTM Zone 44N (EPSG:32644) for metric analysis.
3. Uses the depression-depth raster from the upstream hydrological conditioning step,
   where depression depth is: filled DEM - original DEM.
4. Classifies depression depth into interpretable terrain-depression candidate tiers.
5. Produces an analysis-grade GeoTIFF, methodology sidecar, static map, and interactive
   web map.

## Candidate tiers

| Depth band | Tier | Meaning |
|---|---|---|
| < 0.2 m | Background | below terrain-depression candidate threshold |
| 0.2 - 0.5 m | Minor candidate | shallow terrain-depression signal |
| 0.5 - 2.0 m | High candidate | stronger terrain-depression signal |
| 2.0 - 3.0 m | Deep transition | deeper terrain-depression signal |
| > 3.0 m | Deep terrain-depression | deep terrain feature (not assumed to be a channel) |

"High candidate" refers only to the depression-depth tier. It does NOT mean high
probability of observed waterlogging.

## Current V2.1.1 result

The generated raster contains 514,407 valid cells. Using the >= 0.2 m candidate threshold:

| Tier | Cells | Approx. area |
|---|---:|---:|
| Minor candidate (0.2-0.5 m) | 35,751 | 30.21 km2 |
| High candidate (0.5-2.0 m) | 82,147 | 69.43 km2 |
| Deep transition (2.0-3.0 m) | 15,332 | 12.96 km2 |
| Deep terrain-depression (>3.0 m) | 10,796 | 9.12 km2 |

These describe terrain-depression candidates only and should not be interpreted as
observed or predicted waterlogging area.

## Method & spatial referencing

- **Single analysis CRS = UTM 44N.** All hydrological and terrain-processing steps are
  performed in the projected metric CRS. The tiering step validates that its input raster
  is EPSG:32644. Analysis rasters are not repeatedly reprojected during processing.
- **WGS84 only for display.** Only the visualization layer is reprojected to EPSG:4326 for
  web display, keeping the analysis raster in its original projected CRS.
- **Explicit NoData handling.** -9999 NoData (GDAL/QGIS-safe), with a validity mask
  excluding non-finite, NoData, and physically-impossible negative depths.
- **Fail-fast validation.** The tiering step hard-errors if the input CRS isn't UTM 44N,
  and records the actual raster resolution in the methodology sidecar.

## Outputs

    outputs/
    ├── candidate_depressions.tif              # tier-coded raster (UTM 44N, nodata=-9999)
    ├── candidate_depressions_methodology.txt  # auto-generated methodology / metadata
    ├── depression_tier_map.png                # static report-quality map
    └── depression_tier_map.html               # interactive Folium map

## Setup & run

    python3 -m venv venv
    source venv/bin/activate
    pip install pysheds rasterio folium matplotlib numpy branca

    # 1) Download Copernicus GLO-30 DEM for Noida from OpenTopography (GeoTIFF)
    #    -> place at data/noida_dem.tif
    # 2) hydrology -> TWI + depression depth
    python3 src/noida_waterlogging_v2.py
    # 3) tiered susceptibility map (FROZEN V2.1.1)
    python3 src/tier_map.py

Data source: Copernicus GLO-30 DEM via OpenTopography, bbox ~ 77.23-77.43 E, 28.48-28.68 N.

## Scientific limitations

- Terrain depression is a susceptibility indicator, not evidence of observed waterlogging.
- At ~30 m resolution, fine street-level detail is not captured — results are city-level.
- A deep depression is not assumed to be a drainage channel; that requires independent
  flow-accumulation or drainage-network evidence.
- Where drainage or observed-waterlogging data are unavailable, the gap is documented,
  never fabricated.

## Roadmap

| Stage | Focus | Status |
|---|---|---|
| V1 | DEM -> hydrology -> TWI + depression depth | done |
| V2.1.1 | Tiered terrain-depression candidates | FROZEN |
| V3 | Spatial / DEM-artifact validation | next |
| V4 | Depression x flow-accumulation cross-check | planned |
| V5 | Rainfall integration (event-conditioned) | planned |
| V6 | Urban context (OSM roads, buildings, land-use) | planned |
| V7 | Validation vs reported waterlogging + ML only if labels suffice | planned |

If sufficient labelled historical waterlogging data can't be collected, the system
intentionally stays an interpretable GIS/hydrological baseline rather than attaching an
unjustified ML/"AI" label. Honesty over hype.

## Tech stack

Python, pysheds, rasterio, NumPy, Matplotlib, Folium, Copernicus GLO-30, UTM 44N.
