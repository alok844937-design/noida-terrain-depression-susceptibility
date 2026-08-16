"""
compute_flow.py — Flow accumulation raster + provenance/distribution audit
==========================================================================
Reproduces the EXACT V2 hydrological chain (same input, same steps) and SAVES
the flow-accumulation raster that V2 computed but discarded. Grid is inherited
directly from data/noida_dem_utm.tif so downstream stages (V4) can validate
alignment against candidate_depressions.tif.

Methodological note: this is V2's identical chain. Whether the output is
bit-identical to V2's in-memory acc depends on the same library versions and
the same input DEM; we do NOT claim bit-for-bit — we VERIFY via the audit below.

Input:
    data/noida_dem_utm.tif
Output:
    outputs/flow_accumulation_utm.tif   (UTM 44N, nodata=-9999, grid inherited)
Prints:
    grid/provenance audit + valid-cell accumulation distribution
"""
import numpy as np
import rasterio
from pysheds.grid import Grid

DEM_UTM      = "data/noida_dem_utm.tif"
OUT_ACC      = "outputs/flow_accumulation_utm.tif"
EXPECTED_CRS = "EPSG:32644"
NODATA       = -9999.0


def main():
    # ---- input CRS guard ----
    with rasterio.open(DEM_UTM) as src:
        if src.crs is None or src.crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"{DEM_UTM}: expected {EXPECTED_CRS}, found {src.crs}")
        ref_profile = src.profile
        ref_transform = src.transform
        ref_wh = (src.width, src.height)
        dem_nod = src.nodata

    # ---- EXACT V2 chain (no changes) ----
    grid = Grid.from_raster(DEM_UTM)
    dem  = grid.read_raster(DEM_UTM)
    pit_filled = grid.fill_pits(dem)
    flooded    = grid.fill_depressions(pit_filled)
    inflated   = grid.resolve_flats(flooded)
    fdir       = grid.flowdir(inflated)
    acc        = grid.accumulation(fdir)

    acc_arr = np.asarray(acc, dtype="float64")

    # ---- valid mask (inherit DEM validity; same basis as V2) ----
    dem_arr = np.asarray(dem, dtype="float64")
    nod = dem_nod if dem_nod is not None else NODATA
    valid = np.isfinite(dem_arr) & (dem_arr != nod) & np.isfinite(acc_arr)

    # ---- save flow-acc, grid inherited directly from DEM_UTM ----
    out = np.where(valid, acc_arr, NODATA).astype("float32")
    prof = ref_profile.copy()
    prof.update(dtype="float32", count=1, nodata=NODATA, compress="deflate")
    with rasterio.open(OUT_ACC, "w", **prof) as dst:
        dst.write(out, 1)
        dst.set_band_description(1, "Flow accumulation (D8, upslope cell count)")
        dst.update_tags(SOURCE="pysheds D8 accumulation; V2 chain",
                        INPUT=DEM_UTM, ANALYSIS_CRS=EXPECTED_CRS)
    print(f"[ok] wrote {OUT_ACC}")

    # ---- PROVENANCE / GRID AUDIT ----
    with rasterio.open(OUT_ACC) as a:
        print("\n=== GRID / PROVENANCE AUDIT ===")
        print(f"  CRS         : {a.crs}")
        print(f"  dimensions  : {a.width} x {a.height}")
        print(f"  resolution  : {a.res[0]:.4f} x {a.res[1]:.4f} m")
        print(f"  transform   : {tuple(round(v,4) for v in a.transform[:6])}")
        print(f"  bounds      : {tuple(round(v,2) for v in a.bounds)}")
        print(f"  nodata      : {a.nodata}")
        print(f"  dtype       : {a.dtypes[0]}")
        # grid must match the DEM it was inherited from
        same_wh = (a.width, a.height) == ref_wh
        same_tf = np.allclose(np.array(a.transform), np.array(ref_transform),
                              rtol=0, atol=1e-6)
        print(f"  grid == DEM : dims={same_wh}, transform={same_tf}")

    # ---- DISTRIBUTION AUDIT (valid cells only) ----
    v = acc_arr[valid]
    n_valid = v.size
    n_zero_or_neg = int((v <= 0).sum())
    n_positive = int((v > 0).sum())
    print("\n=== ACCUMULATION DISTRIBUTION (valid cells) ===")
    print(f"  valid cells        : {n_valid:,}")
    print(f"  zero / non-positive: {n_zero_or_neg:,}")
    print(f"  positive cells     : {n_positive:,}")
    print(f"  min                : {np.min(v):.3f}")
    for q in [50, 75, 90, 95, 99]:
        print(f"  P{q:<2d}                : {np.percentile(v, q):.3f}")
    print(f"  max                : {np.max(v):.3f}")
    # heavy-tail signal: how concentrated is the mass?
    print("\n=== TAIL BEHAVIOUR (heavy-tail check) ===")
    print(f"  mean               : {np.mean(v):.3f}")
    print(f"  median (P50)       : {np.percentile(v,50):.3f}")
    print(f"  max / P99 ratio    : {np.max(v)/max(np.percentile(v,99),1e-9):.1f}x")
    print(f"  P99 / P50 ratio    : {np.percentile(v,99)/max(np.percentile(v,50),1e-9):.1f}x")
    print("\n  (Interpretation deferred: do NOT freeze V4 thresholds from these")
    print("   raw percentiles until the tail shape is reviewed.)")


if __name__ == "__main__":
    main()
