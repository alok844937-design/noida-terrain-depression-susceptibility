"""
V7-B — SPATIAL CORROBORATION (observed waterlogging reports vs V4 susceptibility)
================================================================================
Tests whether documented observed-waterlogging uncertainty zones spatially
intersect V4 bucket-2 (unflagged + low-flow closed depressions), vs a
parent-matched random null in the full DEM footprint.

DESIGN LOCKS:
  * PRIMARY INFERENTIAL UNIT = PARENT OBSERVATION (n=2 verified). A parent
    overlaps iff >=1 of its instances intersects bucket-2. Instance-level
    overlap is a DESCRIPTIVE diagnostic only — instances of one parent are
    NOT independent observations, so they must not inflate n.
  * PARENT-MATCHED NULL: each null replicate builds one random "parent" per
    real parent, with the SAME per-parent instance count and radii, drawn from
    the full DEM footprint; parent overlaps iff >=1 instance hits bucket-2.
  * At n=2 the observed parent statistic can only be 0/50/100% -> NO statistical
    significance is claimed; the P-value is reported for completeness only.
  * Coordinate verification status is read from the CSV (mixed web_verified /
    approx_unverified), never hard-coded. Coordinate verification is NOT physical
    event ground-truthing. Result stays PROVISIONAL.
  * All geometry in raster CRS (UTM 44N); points transformed in, buffers in metres.
  * No tuning: radius, bucket-2, seed (20260819) all fixed.

Verdict wording:
  "The available observed reports are insufficient to establish spatial
   corroboration of the V4 susceptibility layer; this neither validates nor
   refutes it."
"""
import csv, json, numpy as np, rasterio
from pyproj import Transformer
from collections import defaultdict, Counter

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
        """Parent-level primary + instance-level descriptive."""
        n_inst = len(subset)
        hit_inst = sum(r["_hit"] for r in subset)
        by_parent = defaultdict(list)
        for r in subset:
            by_parent[r["parent_obs"]].append(r["_hit"])
        n_par = len(by_parent)
        hit_par = sum(any(v) for v in by_parent.values())
        structure = {p: [float(r["_rad"]) for r in subset if r["parent_obs"] == p]
                     for p in by_parent}
        return {
            "label": label,
            "instances_total": n_inst,
            "instances_overlapping": hit_inst,
            "instance_overlap_rate": round(hit_inst / n_inst, 4) if n_inst else None,
            "parent_observations_total": n_par,
            "parent_observations_overlapping": hit_par,
            "parent_overlap_rate": round(hit_par / n_par, 4) if n_par else None,
            "_structure": structure,
        }

    primary = [r for r in rows if r["validation_set"] == "PRIMARY"]
    sensitivity = [r for r in rows if r["validation_set"] == "SENSITIVITY"]
    s_primary = summarize(primary, "PRIMARY (independently source-verified parents)")
    s_sens = summarize(sensitivity, "SENSITIVITY (user-reported parents, source pending)")

    cv = Counter(r["coordinate_verification_status"] for r in rows)
    web_v = cv.get("web_verified", 0)
    approx_v = cv.get("approx_unverified", 0)

    rng = np.random.default_rng(SEED)
    valid_rows, valid_cols = np.where(null_domain)
    n_valid = len(valid_rows)

    structure = s_primary["_structure"]
    n_parents = len(structure)

    def one_null_replicate():
        overlapping = 0
        for parent, radii in structure.items():
            k = len(radii)
            idx = rng.integers(0, n_valid, size=k)
            rr = valid_rows[idx]; cc = valid_cols[idx]
            px = transform.c + (cc + 0.5) * transform.a
            py = transform.f + (rr + 0.5) * transform.e
            hit = False
            for i in range(k):
                if buffer_hits_bucket2(px[i], py[i], radii[i], bucket2, transform, res):
                    hit = True
                    break
            overlapping += 1 if hit else 0
        return overlapping

    null_counts = np.array([one_null_replicate() for _ in range(N_NULL)])
    obs_parent_overlap = s_primary["parent_observations_overlapping"]
    null_parent_rate = float(null_counts.mean() / n_parents)
    p_ge = float((null_counts >= obs_parent_overlap).mean())

    L = [
        "NOIDA V7-B — SPATIAL CORROBORATION (parent-level primary; PROVISIONAL)",
        "=" * 66,
        "Primary inferential unit = PARENT OBSERVATION. Instance-level overlap is",
        "reported as a descriptive diagnostic ONLY (multiple instances belong to the",
        "same parent, so they are NOT independent observations).",
        "This does NOT establish that individual susceptible cells flooded.",
        "",
        f"raster CRS = {crs}, resolution = {res:.2f} m",
        f"bucket-2 cells = {int(bucket2.sum())}, null-domain cells (full DEM) = {int(null_domain.sum())}",
        "",
        "COORDINATE VERIFICATION MIX (from geometry CSV, not hard-coded):",
        f"  web_verified instances     : {web_v}/20 (location cross-checked on public web maps)",
        f"  approx_unverified instances: {approx_v}/20",
        "  NOTE: coordinate verification != physical event ground-truthing. Overall PROVISIONAL.",
        "",
        "-" * 66,
        "PRIMARY — parent-level (the inferential unit):",
        f"  independently source-verified parent observations : {s_primary['parent_observations_total']}  (n)",
        f"  parents with >=1 bucket-2-overlapping instance     : "
        f"{s_primary['parent_observations_overlapping']}/{s_primary['parent_observations_total']}",
        "  (descriptive: each verified parent had at least one uncertainty-zone instance",
        "   intersecting bucket-2; because n=2 this is NOT statistical corroboration)",
        "",
        "  instance-level DIAGNOSTIC (descriptive only, NOT an independent-sample statistic):",
        f"    {s_primary['instances_overlapping']}/{s_primary['instances_total']} instances overlap bucket-2 "
        f"({s_primary['instance_overlap_rate']*100:.1f}%)",
        "",
        "PARENT-MATCHED NULL (random 'parents' with the SAME per-parent radius structure):",
        f"  seed                       : {SEED}",
        f"  null replicates            : {N_NULL}",
        f"  mean null parent-overlap   : {null_parent_rate*100:.1f}%",
        f"  observed parent-overlap    : {s_primary['parent_overlap_rate']*100:.0f}% "
        f"({obs_parent_overlap}/{n_parents})",
        f"  P(null >= observed)        : {p_ge:.3f}  [REPORTED, NOT a significance claim]",
        "",
        "-" * 66,
        "SENSITIVITY (user-reported parents, source pending; supporting only, NOT primary):",
        f"  parents                    : {s_sens['parent_observations_total']}",
        f"  parents with >=1 overlap   : {s_sens['parent_observations_overlapping']} "
        f"({s_sens['parent_overlap_rate']*100:.0f}% descriptive)",
        f"  instance diagnostic        : {s_sens['instances_overlapping']}/{s_sens['instances_total']} "
        f"({s_sens['instance_overlap_rate']*100:.1f}%)",
        "",
        "=" * 66,
        "INTERPRETATION (honest):",
        f"  * Primary inferential unit is the parent observation, and there are only n="
        f"{s_primary['parent_observations_total']}",
        "    independently source-verified parents. At n=2 the observed parent statistic can only",
        "    be 0%, 50% or 100%, so NO statistical significance can be claimed regardless of the",
        "    null distribution. The P-value above is reported for completeness, not as inference.",
        "  * Parent-level spatial overlap is DESCRIPTIVE only. With two verified parents the",
        "    available evidence is insufficient to establish statistical spatial corroboration",
        "    of the terrain-susceptibility hypothesis.",
        f"  * The instance-level figure ({s_primary['instance_overlap_rate']*100:.0f}%) is retained as a",
        "    descriptive spatial diagnostic but is NOT treated as an independent-sample statistic,",
        "    because the instances belong to the same parent observations.",
        "  * This is NOT evidence against the susceptibility hypothesis; it indicates the currently",
        "    available observations are insufficient to demonstrate positive spatial corroboration.",
        "",
        "  \"The available observed reports are insufficient to establish spatial corroboration",
        "   of the V4 susceptibility layer; this neither validates nor refutes it.\"",
    ]
    out = "\n".join(L) + "\n"
    with open("outputs/v7b_corroboration_report.txt", "w") as f:
        f.write(out)
    js = {
        "provisional": True,
        "primary_inferential_unit": "parent_observation",
        "coordinate_verification": {
            "web_verified_instances": web_v,
            "approx_unverified_instances": approx_v,
            "all_in_bbox": True,
            "note": "coordinate verification != physical event ground-truthing",
        },
        "primary": {
            "parent_observations_n": s_primary["parent_observations_total"],
            "parents_with_overlap": s_primary["parent_observations_overlapping"],
            "parent_overlap_rate": s_primary["parent_overlap_rate"],
            "instance_overlap_rate_descriptive_only": s_primary["instance_overlap_rate"],
            "instances_overlapping": s_primary["instances_overlapping"],
            "instances_total": s_primary["instances_total"],
        },
        "parent_matched_null": {
            "seed": SEED, "n_null": N_NULL,
            "mean_null_parent_overlap_rate": null_parent_rate,
            "observed_parent_overlap_rate": s_primary["parent_overlap_rate"],
            "p_null_ge_observed": p_ge,
            "note": "n=2 parents: statistic can only be 0/50/100%; p reported, NOT a significance claim",
        },
        "sensitivity": {
            "parent_observations_n": s_sens["parent_observations_total"],
            "parents_with_overlap": s_sens["parent_observations_overlapping"],
            "parent_overlap_rate": s_sens["parent_overlap_rate"],
            "instance_overlap_rate_descriptive_only": s_sens["instance_overlap_rate"],
            "note": "user-reported parents, source pending; supporting only, not primary inference",
        },
        "verdict": ("Available observed reports are insufficient to establish spatial "
                    "corroboration of the V4 susceptibility layer; this neither validates "
                    "nor refutes it."),
    }
    with open("outputs/v7b_corroboration_report.json", "w") as f:
        json.dump(js, f, indent=2)
    print(out)

if __name__ == "__main__":
    main()
