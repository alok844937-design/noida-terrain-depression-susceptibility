"""
V7-B — COARSE SPATIAL CORROBORATION (observed waterlogging reports vs V4 susceptibility)
=======================================================================================
Observed uncertainty zones vs V4 bucket-2, compared to a null model of random
points in the FULL Noida DEM footprint (NOT the V4 evidence raster, which only
covers tier-4 cells and is 74% bucket-2 -> circular).

HONESTY LOCKS: approx_unverified coords (PROVISIONAL); uncertainty-zone scale, not
per-cell; TWO units (parent-observation = statistical n=2 primary; instance = spatial);
PRIMARY=verified only, SENSITIVITY=user-reported; null = 10,000 pts in full DEM mask,
same radii mix, seed 20260819, EXPLORATORY; all geometry in raster CRS (UTM 44N).
Wording: "Observed waterlogging reports were spatially corroborated against the V4
susceptibility layer at uncertainty-zone scale; this does not establish that individual
susceptible cells flooded."
"""
import csv, json, numpy as np, rasterio
from pyproj import Transformer
from collections import defaultdict

EVIDENCE_TIF = "outputs/flow_crosscheck_evidence.tif"  # V4: ==2 is bucket-2
DEM_TIF      = "data/noida_dem_utm.tif"                 # full analysis footprint (null domain)
GEOM_CSV     = "outputs/v7b_geometry.csv"
BUCKET2_VAL  = 2
SEED         = 20260819
N_NULL       = 10000

def load_bucket2():
    with rasterio.open(EVIDENCE_TIF) as ds:
        arr = ds.read(1)
        transform = ds.transform
        crs = ds.crs
        res = abs(transform.a)
        eshape = arr.shape
    bucket2 = (arr == BUCKET2_VAL)
    with rasterio.open(DEM_TIF) as dd:
        dem = dd.read(1)
        dem_nodata = dd.nodata
        dtransform = dd.transform
        dcrs = dd.crs
    assert dem.shape == eshape, f"grid mismatch DEM {dem.shape} vs evidence {eshape}"
    assert dcrs == crs, f"CRS mismatch DEM {dcrs} vs evidence {crs}"
    assert np.allclose([dtransform.a, dtransform.e, dtransform.c, dtransform.f],
                       [transform.a, transform.e, transform.c, transform.f]), \
        "transform mismatch DEM vs evidence"
    if dem_nodata is None:
        null_domain = np.ones_like(dem, dtype=bool)
    else:
        null_domain = (dem != dem_nodata) & np.isfinite(dem)
    return bucket2, null_domain, transform, crs, res, arr

def buffer_hits_bucket2(px, py, radius_m, bucket2, transform, res):
    inv = ~transform
    col_f, row_f = inv * (px, py)
    rad_cells = int(np.ceil(radius_m / res)) + 1
    r0 = max(0, int(np.floor(row_f)) - rad_cells)
    r1 = min(bucket2.shape[0], int(np.ceil(row_f)) + rad_cells + 1)
    c0 = max(0, int(np.floor(col_f)) - rad_cells)
    c1 = min(bucket2.shape[1], int(np.ceil(col_f)) + rad_cells + 1)
    if r0 >= r1 or c0 >= c1:
        return False
    sub = bucket2[r0:r1, c0:c1]
    if not sub.any():
        return False
    rows = np.arange(r0, r1)
    cols = np.arange(c0, c1)
    cx = transform.c + (cols + 0.5) * transform.a
    cy = transform.f + (rows + 0.5) * transform.e
    dx = cx[None, :] - px
    dy = cy[:, None] - py
    dist2 = dx**2 + dy**2
    return bool((sub & (dist2 <= radius_m**2)).any())

def main():
    bucket2, null_domain, transform, crs, res, arr = load_bucket2()
    print(f"raster CRS={crs}, res={res:.2f} m, bucket-2 cells={int(bucket2.sum())}, "
          f"null-domain (full DEM) cells={int(null_domain.sum())}")

    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    rows = list(csv.DictReader(open(GEOM_CSV)))
    for r in rows:
        x, y = tf.transform(float(r["lon"]), float(r["lat"]))
        r["_x"], r["_y"] = x, y
        r["_rad"] = float(r["uncertainty_radius_m"])
        r["_hit"] = buffer_hits_bucket2(x, y, r["_rad"], bucket2, transform, res)

    def summarize(subset, label):
        n_inst = len(subset)
        hit_inst = sum(r["_hit"] for r in subset)
        by_parent = defaultdict(list)
        for r in subset:
            by_parent[r["parent_obs"]].append(r["_hit"])
        n_par = len(by_parent)
        hit_par = sum(any(v) for v in by_parent.values())
        return {
            "label": label,
            "instances_total": n_inst,
            "instances_overlapping": hit_inst,
            "instance_overlap_rate": round(hit_inst / n_inst, 4) if n_inst else None,
            "parent_observations_total": n_par,
            "parent_observations_corroborated": hit_par,
        }

    primary = [r for r in rows if r["validation_set"] == "PRIMARY"]
    sensitivity = [r for r in rows if r["validation_set"] == "SENSITIVITY"]
    s_primary = summarize(primary, "PRIMARY (verified parents only)")
    s_sens = summarize(sensitivity, "SENSITIVITY (user-reported parents)")

    rng = np.random.default_rng(SEED)
    valid_rows, valid_cols = np.where(null_domain)
    n_valid = len(valid_rows)
    primary_radii = np.array([r["_rad"] for r in primary])

    def null_rate_for_radii(radii, n_samples):
        idx = rng.integers(0, n_valid, size=n_samples)
        rr = valid_rows[idx]; cc = valid_cols[idx]
        px = transform.c + (cc + 0.5) * transform.a
        py = transform.f + (rr + 0.5) * transform.e
        rad = rng.choice(radii, size=n_samples, replace=True)
        hits = 0
        for i in range(n_samples):
            if buffer_hits_bucket2(px[i], py[i], rad[i], bucket2, transform, res):
                hits += 1
        return hits / n_samples

    null_primary = null_rate_for_radii(primary_radii, N_NULL)
    obs_primary_rate = s_primary["instance_overlap_rate"]
    B = 2000
    boot = np.empty(B)
    for b in range(B):
        idx = rng.integers(0, n_valid, size=len(primary))
        rr = valid_rows[idx]; cc = valid_cols[idx]
        px = transform.c + (cc + 0.5) * transform.a
        py = transform.f + (rr + 0.5) * transform.e
        rad = rng.choice(primary_radii, size=len(primary), replace=True)
        h = sum(buffer_hits_bucket2(px[i], py[i], rad[i], bucket2, transform, res)
                for i in range(len(primary)))
        boot[b] = h / len(primary)
    p_ge = float((boot >= obs_primary_rate).mean())

    L = [
        "NOIDA V7-B — COARSE SPATIAL CORROBORATION (EXPLORATORY, PROVISIONAL)",
        "=" * 66,
        "Observed waterlogging reports vs V4 bucket-2 susceptibility, at",
        "uncertainty-zone scale. Coordinates are approx_unverified -> PROVISIONAL.",
        "This does NOT establish that individual susceptible cells flooded.",
        "",
        f"raster CRS = {crs}, resolution = {res:.2f} m",
        f"bucket-2 cells = {int(bucket2.sum())}, null-domain cells (full DEM) = {int(null_domain.sum())}",
        "",
        "PRIMARY (independently verified parents only):",
        f"  parent observations           : {s_primary['parent_observations_total']} (STATISTICAL UNIT)",
        f"  parent obs corroborated       : {s_primary['parent_observations_corroborated']}",
        f"  location instances            : {s_primary['instances_total']} (spatial unit)",
        f"  instances overlapping bucket-2: {s_primary['instances_overlapping']} "
        f"({s_primary['instance_overlap_rate']*100:.1f}%)",
        "",
        "SENSITIVITY (user-reported parents, source pending):",
        f"  parent observations           : {s_sens['parent_observations_total']}",
        f"  parent obs corroborated       : {s_sens['parent_observations_corroborated']}",
        f"  location instances            : {s_sens['instances_total']}",
        f"  instances overlapping bucket-2: {s_sens['instances_overlapping']} "
        f"({s_sens['instance_overlap_rate']*100:.1f}%)",
        "",
        "NULL MODEL (random points in FULL DEM footprint, same radius mix):",
        f"  seed                          : {SEED}",
        f"  null samples                  : {N_NULL}",
        f"  null instance-overlap rate    : {null_primary*100:.1f}%",
        f"  observed PRIMARY instance rate: {obs_primary_rate*100:.1f}%",
        f"  difference (obs - null)       : {(obs_primary_rate-null_primary)*100:+.1f} pts",
        f"  bootstrap P(null >= observed) : {p_ge:.3f}  [EXPLORATORY, n={len(primary)} instances]",
        "",
        "INTERPRETATION",
        "  Exploratory spatial comparison only. With just 2 verified parent",
        "  observations, no statistical power is claimed. The null comparison",
        "  indicates whether observed reports intersect susceptibility more than",
        "  random locations across Noida would, at coarse uncertainty-zone scale.",
        "",
        "  \"Observed waterlogging reports were spatially corroborated against the",
        "   V4 susceptibility layer at uncertainty-zone scale; this does not",
        "   establish that individual susceptible cells flooded.\"",
    ]
    out = "\n".join(L) + "\n"
    with open("outputs/v7b_corroboration_report.txt", "w") as f:
        f.write(out)
    js = {
        "provisional": True,
        "coordinates": "approx_unverified",
        "null_domain": "full_dem_footprint",
        "primary": s_primary,
        "sensitivity": s_sens,
        "null_model": {
            "seed": SEED, "n_null": N_NULL,
            "null_instance_overlap_rate": null_primary,
            "observed_primary_instance_rate": obs_primary_rate,
            "difference_pts": obs_primary_rate - null_primary,
            "bootstrap_p_null_ge_observed": p_ge,
            "bootstrap_B": B,
            "exploratory": True,
        },
        "wording": ("Observed waterlogging reports were spatially corroborated "
                    "against the V4 susceptibility layer at uncertainty-zone scale; "
                    "this does not establish that individual susceptible cells flooded."),
    }
    with open("outputs/v7b_corroboration_report.json", "w") as f:
        json.dump(js, f, indent=2)
    print(out)

if __name__ == "__main__":
    main()
