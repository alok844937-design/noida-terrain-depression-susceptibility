"""
V4 — Depression x Flow-Accumulation cross-check (DIAGNOSTIC / EVIDENCE ONLY)
===========================================================================
Cross-references DEEP terrain-depression candidates (tier 4, >3 m) against
D8 flow accumulation to add an independent HYDROLOGICAL evidence axis to V3's
SPATIAL evidence axis.

CRITICAL FRAMING (locked):
  Low or no flow support is NOT evidence of an artifact. A genuine closed
  depression / pond accumulates little upslope flow yet is real. Flow is one
  evidence axis, not a verdict. V4 removes / reclassifies NOTHING. V2.1.1 stays
  FROZEN.

Flow-accumulation bands are LOG-SCALE (accumulation is extremely heavy-tailed:
observed P50=2, P99~4378, max~96280 -> linear percentile bands are meaningless):
    acc <  10        negligible
    10  <= acc < 100 minor
    100 <= acc <1000 moderate
    acc >=1000       strong (channel-like)

Inputs:
    outputs/candidate_depressions.tif       (tier raster, UTM 44N, FROZEN V2.1.1)
    outputs/flow_accumulation_utm.tif       (D8 accumulation, UTM 44N)
    outputs/artifact_suspect_flags.tif      (V3 flags: 1 unflagged-deep, 2 suspect)

Outputs (outputs/):
    flow_crosscheck_report.txt
    flow_crosscheck_evidence.tif    (deep-cell evidence-bucket raster)
    flow_crosscheck_map.png
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

TIER_RASTER  = "outputs/candidate_depressions.tif"
ACC_RASTER   = "outputs/flow_accumulation_utm.tif"
V3_FLAGS     = "outputs/artifact_suspect_flags.tif"
EXPECTED_CRS = "EPSG:32644"
NODATA       = -9999.0
DEEP_TIER    = 4

# ---- FROZEN V4 flow bands (log-scale; heavy-tailed accumulation) ----
FLOW_BANDS = [
    ("negligible", 0,    10),
    ("minor",      10,   100),
    ("moderate",   100,  1000),
    ("strong",     1000, np.inf),
]


def load(path):
    with rasterio.open(path) as src:
        if src.crs is None or src.crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"{path}: expected {EXPECTED_CRS}, found {src.crs}")
        arr = src.read(1).astype("float64")
        profile, bounds, nod = src.profile, src.bounds, src.nodata
        wh, tf = (src.width, src.height), src.transform
    return arr, profile, bounds, nod, wh, tf


def assert_same_grid(name_a, wh_a, tf_a, name_b, wh_b, tf_b):
    if wh_a != wh_b:
        raise ValueError(f"{name_a} vs {name_b}: dimension mismatch {wh_a} != {wh_b}")
    if not np.allclose(np.array(tf_a), np.array(tf_b), rtol=0, atol=1e-6):
        raise ValueError(f"{name_a} vs {name_b}: transform mismatch (grids differ)")


def flow_band_code(acc):
    """acc value -> band index 0..3 (negligible..strong)."""
    out = np.zeros(acc.shape, dtype="int16")
    for code, (_, lo, hi) in enumerate(FLOW_BANDS):
        out[(acc >= lo) & (acc < hi)] = code
    return out


def main():
    tiers, profile, bounds, _, wh_t, tf_t = load(TIER_RASTER)
    acc,   _,       _,      acc_nod, wh_a, tf_a = load(ACC_RASTER)
    v3,    _,       _,      _,       wh_v, tf_v = load(V3_FLAGS)

    # ---- grid/provenance validation across all three rasters ----
    assert_same_grid("tier", wh_t, tf_t, "acc", wh_a, tf_a)
    assert_same_grid("tier", wh_t, tf_t, "v3flags", wh_v, tf_v)

    t = profile["transform"]
    cell_area_m2 = abs(t.a * t.e)

    deep = (tiers == DEEP_TIER)
    n_deep = int(deep.sum())
    if n_deep == 0:
        print("No deep (>3 m) candidate cells. Nothing to cross-check.")
        return

    acc_valid = np.isfinite(acc) & (acc != (acc_nod if acc_nod is not None else NODATA))

    # ---- whole-raster + tier-4 accumulation distribution (audit) ----
    def pct_line(a):
        return {q: float(np.percentile(a, q)) for q in [50, 75, 90, 95, 99]}
    whole = acc[acc_valid & (acc > 0)]
    deep_acc = acc[deep & acc_valid]
    whole_p = pct_line(whole)
    deep_p  = pct_line(deep_acc) if deep_acc.size else {q: float("nan") for q in [50,75,90,95,99]}

    # ---- flow bands over deep cells ----
    bands = flow_band_code(acc)
    band_counts_deep = {FLOW_BANDS[c][0]: int((deep & acc_valid & (bands == c)).sum())
                        for c in range(len(FLOW_BANDS))}

    # ---- V3 axis: suspect (2) vs unflagged (1) among deep ----
    v3_suspect   = deep & (v3 == 2)
    v3_unflagged = deep & (v3 == 1)

    # ---- 2-axis evidence matrix: V3(2) x flow(4) ----
    # strong/moderate flow = "flow-supported"; minor/negligible = "low flow"
    flow_supported = deep & acc_valid & (bands >= 2)   # moderate or strong
    low_flow       = deep & acc_valid & (bands < 2)    # minor or negligible

    # evidence buckets (diagnostic, NOT verdicts):
    #  1 unflagged + flow-supported  -> strongest real-feature evidence
    #  2 unflagged + low-flow        -> plausible closed depression
    #  3 suspect   + flow-supported  -> conflicting evidence (human review)
    #  4 suspect   + low-flow        -> most artifact-like (two weak signals)
    ev = np.zeros(tiers.shape, dtype="float32")
    ev[v3_unflagged & flow_supported] = 1
    ev[v3_unflagged & low_flow]       = 2
    ev[v3_suspect   & flow_supported] = 3
    ev[v3_suspect   & low_flow]       = 4
    ev[~deep] = NODATA
    counts = {k: int((ev == k).sum()) for k in [1, 2, 3, 4]}

    # ---- save evidence raster (grid inherited) ----
    profile.update(dtype="float32", count=1, nodata=NODATA, compress="deflate")
    with rasterio.open("outputs/flow_crosscheck_evidence.tif", "w", **profile) as dst:
        dst.write(ev, 1)
        dst.set_band_description(1, "V4 evidence bucket (1..4)")
    print("[ok] wrote outputs/flow_crosscheck_evidence.tif")

    # ---- report ----
    L = [
        "NOIDA V4 — DEPRESSION x FLOW-ACCUMULATION CROSS-CHECK (evidence only)",
        "=" * 68,
        "Adds an independent HYDROLOGICAL evidence axis to V3's SPATIAL axis.",
        "Low/no flow support is NOT evidence of an artifact (a real closed",
        "depression accumulates little upslope flow). V4 removes/reclassifies",
        "NOTHING. V2.1.1 stays FROZEN. Grids validated (dims+transform) across",
        "tier, accumulation, and V3-flag rasters before analysis.",
        "",
        f"Analysis CRS            : {EXPECTED_CRS}",
        f"Cell area               : {cell_area_m2:,.0f} m^2",
        f"Deep (>3 m) cells       : {n_deep:,}",
        "",
        "FLOW BANDS (log-scale; accumulation is heavy-tailed)",
        "  negligible : acc < 10",
        "  minor      : 10 <= acc < 100",
        "  moderate   : 100 <= acc < 1000",
        "  strong     : acc >= 1000",
        "",
        "ACCUMULATION DISTRIBUTION (percentiles)",
        f"  whole-raster (acc>0) : P50={whole_p[50]:.1f} P75={whole_p[75]:.1f} "
        f"P90={whole_p[90]:.1f} P95={whole_p[95]:.1f} P99={whole_p[99]:.1f}",
        f"  tier-4 deep cells    : P50={deep_p[50]:.1f} P75={deep_p[75]:.1f} "
        f"P90={deep_p[90]:.1f} P95={deep_p[95]:.1f} P99={deep_p[99]:.1f}",
        "",
        "FLOW BAND COUNTS (deep cells)",
    ]
    for name, _, _ in FLOW_BANDS:
        n = band_counts_deep[name]
        L.append(f"  {name:11s}: {n:7,} ({100*n/n_deep:5.1f}% of deep)")
    L += [
        "",
        "V3 x FLOW EVIDENCE MATRIX (deep cells; diagnostic buckets, NOT verdicts)",
        f"  [1] V3-unflagged + flow-supported : {counts[1]:7,}  strongest positive evidence of a coherent topographic/hydrological feature",
        f"  [2] V3-unflagged + low-flow       : {counts[2]:7,}  plausible closed depression",
        f"  [3] V3-suspect   + flow-supported : {counts[3]:7,}  conflicting -> human review",
        f"  [4] V3-suspect   + low-flow       : {counts[4]:7,}  highest-priority artifact-suspect review (two weak signals)",
        "",
        "INTERPRETATION",
        "  These are evidence buckets combining two independent diagnostics, not",
        "  confirmations. Bucket 4 (spatially suspect AND low hydrological support)",
        "  is the highest-priority for further validation; bucket 1 has the strongest",
        "  positive evidence of a coherent topographic/hydrological feature.",
        "  Buckets 2 and 3 are genuinely ambiguous by design. NO cell is removed or",
        "  reclassified; V2.1.1 remains frozen. 'flow-supported' = moderate/strong;",
        "  'low-flow' = minor/negligible. Low flow does NOT imply artifact.",
        "",
        "  V4 does not identify DEM artifacts; it prioritizes candidates for further",
        "  validation by combining spatial and hydrological evidence.",
    ]
    with open("outputs/flow_crosscheck_report.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/flow_crosscheck_report.txt")

    # ---- map: 4 evidence buckets ----
    view = np.where(ev == NODATA, np.nan, ev)
    colors = ["#1a9850",  # 1 strongest real
              "#91bfdb",  # 2 plausible closed depression
              "#fdae61",  # 3 conflicting
              "#d73027"]  # 4 most artifact-like
    cmap = ListedColormap(colors)
    norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], cmap.N)
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(np.ma.masked_invalid(view), cmap=cmap, norm=norm,
              extent=extent, origin="upper", interpolation="nearest")
    labels = ["Unflagged + flow-supported (coherent feature evidence)",
              "Unflagged + low-flow (plausible closed depression)",
              "Suspect + flow-supported (conflicting)",
              "Suspect + low-flow (highest-priority review)"]
    handles = [Patch(facecolor=colors[i], edgecolor="#555", label=labels[i])
               for i in range(4)]
    ax.legend(handles=handles, loc="lower right", fontsize=7.5, framealpha=0.9)
    ax.set_title("Noida V4 — Deep-candidate evidence (V3 spatial x flow-accumulation)\n"
                 "evidence buckets, NOT verdicts; low flow != artifact; V2.1.1 frozen",
                 fontsize=10.5)
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.savefig("outputs/flow_crosscheck_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("[ok] wrote outputs/flow_crosscheck_map.png")


if __name__ == "__main__":
    main()
