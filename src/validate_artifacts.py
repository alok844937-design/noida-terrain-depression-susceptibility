"""
V3 — Spatial DEM-artifact-suspect diagnostics (DIAGNOSTIC ONLY)
==============================================================
Interrogates DEEP terrain-depression candidates (tier 4, >3 m) — the most
extreme tail — for spatial signatures that RAISE artifact suspicion. It does
NOT assert any cell IS an artifact, does NOT modify the FROZEN V2.1.1 raster,
does NOT use flow accumulation (-> V4), and performs NO removal/filtering.

PRIMARY diagnostics (frozen parameters):
  1. Connected-component size   TINY_PATCH_MAX_CELLS = 2  (tiny/isolated -> suspect)
  2. Neighbourhood-spike        SPIKE_WINDOW_SIZE   = 3  (3x3 immediate 8 neighbours)

Thresholds are heuristic diagnostic thresholds, NOT universal artifact criteria.

Inputs:
    outputs/candidate_depressions.tif   (tier raster, UTM 44N, FROZEN)
    data/noida_dem_utm.tif              (original DEM, UTM 44N)

Outputs (outputs/):
    artifact_suspect_report.txt         report / methodology
    artifact_suspect_flags.tif          per-deep-cell diagnostic raster
    artifact_suspect_map.png            static map
"""
import numpy as np
import rasterio
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

TIER_RASTER  = "outputs/candidate_depressions.tif"
DEM_RASTER   = "data/noida_dem_utm.tif"
EXPECTED_CRS = "EPSG:32644"
NODATA       = -9999.0

# ---- FROZEN V3 PARAMETERS (explicit; no hidden magic numbers) ----
DEEP_TIER            = 4       # >3 m candidate tier — primary population
TINY_PATCH_MAX_CELLS = 2       # patch <= this -> tiny/isolated -> artifact-suspect
SPIKE_WINDOW_SIZE    = 3       # 3x3 immediate neighbourhood
SPIKE_DROP_M         = 3.0     # heuristic: cell >= this below local median -> spike-suspect


def load(path):
    with rasterio.open(path) as src:
        if src.crs is None or src.crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"{path}: expected {EXPECTED_CRS}, found {src.crs}")
        arr = src.read(1).astype("float64")
        profile = src.profile
        bounds = src.bounds
        nod = src.nodata
    return arr, profile, bounds, nod


def validate_grid_alignment():
    """Same CRS is not enough — dimensions and transform must match exactly."""
    with rasterio.open(TIER_RASTER) as t, rasterio.open(DEM_RASTER) as d:
        if t.width != d.width or t.height != d.height:
            raise ValueError(
                "Tier raster and DEM have different dimensions: "
                f"tier={t.width}x{t.height}, dem={d.width}x{d.height}")
        if not np.allclose(np.array(t.transform), np.array(d.transform),
                           rtol=0, atol=1e-6):
            raise ValueError("Tier raster and DEM have different spatial "
                             "transforms. They must be on the same grid.")


def main():
    validate_grid_alignment()

    tiers, profile, bounds, _ = load(TIER_RASTER)
    dem, _, _, dem_nod        = load(DEM_RASTER)

    # generic cell-area (robust for non-square pixels)
    t = profile["transform"]
    cell_area_m2 = abs(t.a * t.e)

    deep = (tiers == DEEP_TIER)
    n_deep = int(deep.sum())
    if n_deep == 0:
        print("No deep (>3 m) candidate cells. Nothing to interrogate.")
        return

    # ---- PRIMARY DIAGNOSTIC 1: connected-component size (8-connectivity) ----
    structure = np.ones((3, 3), dtype=int)
    labels, n_comp = ndimage.label(deep, structure=structure)
    comp_sizes = ndimage.sum(np.ones_like(labels), labels,
                             index=np.arange(1, n_comp + 1))
    size_of_cell = np.zeros_like(labels, dtype="float64")
    for cid in range(1, n_comp + 1):
        size_of_cell[labels == cid] = comp_sizes[cid - 1]
    tiny_suspect = deep & (size_of_cell <= TINY_PATCH_MAX_CELLS)

    # ---- PRIMARY DIAGNOSTIC 2: neighbourhood-spike (3x3 on original DEM) ----
    dem_valid = np.isfinite(dem) & (dem != (dem_nod if dem_nod is not None else NODATA))
    fill_val = np.nanmedian(np.where(dem_valid, dem, np.nan))
    dem_filled = np.where(dem_valid, dem, fill_val)
    local_med = ndimage.median_filter(dem_filled, size=SPIKE_WINDOW_SIZE)

    # only cells whose FULL 3x3 neighbourhood is valid get a spike verdict;
    # edge / nodata-touching cells are excluded from spike evidence.
    valid_neigh_count = ndimage.convolve(
        dem_valid.astype(np.uint8),
        np.ones((SPIKE_WINDOW_SIZE, SPIKE_WINDOW_SIZE), dtype=np.uint8),
        mode="constant", cval=0)
    full_neigh = valid_neigh_count == SPIKE_WINDOW_SIZE ** 2  # exactly 9/9 valid
    drop_below_local = local_med - dem
    spike_suspect = deep & dem_valid & full_neigh & (drop_below_local >= SPIKE_DROP_M)
    spike_excluded_edge = int((deep & ~full_neigh).sum())
    both_suspect = int((deep & tiny_suspect & spike_suspect).sum())

    # ---- combine (diagnostic evidence; NOT artifact assertion) ----
    suspect = deep & (tiny_suspect | spike_suspect)
    unflagged = deep & ~suspect

    # ---- diagnostic raster: 0 bg, 1 unflagged-deep, 2 artifact-suspect ----
    flag = np.zeros(tiers.shape, dtype="float32")
    flag[unflagged] = 1
    flag[suspect]   = 2
    flag[~deep]     = NODATA
    profile.update(dtype="float32", count=1, nodata=NODATA)
    with rasterio.open("outputs/artifact_suspect_flags.tif", "w", **profile) as dst:
        dst.write(flag, 1)
    print("[ok] wrote outputs/artifact_suspect_flags.tif")

    # ---- report ----
    lines = [
        "NOIDA V3 — SPATIAL DEM-ARTIFACT-SUSPECT DIAGNOSTICS",
        "=" * 64,
        "Primary population : DEEP terrain-depression candidates (tier 4, >3 m)",
        "                     — the most extreme tail, interrogated first.",
        "Reports artifact-SUSPECT diagnostic evidence only. Does NOT assert artifacts,",
        "does NOT modify the FROZEN V2.1.1 tier raster, does NOT use flow accumulation",
        "(deferred to V4), and performs NO removal. Grid alignment (dimensions +",
        "transform) between DEM and tier raster is validated before analysis.",
        "",
        f"Analysis CRS            : {EXPECTED_CRS}",
        f"Cell area               : {cell_area_m2:,.0f} m^2 (1 cell)",
        f"Deep (>3 m) cells       : {n_deep:,}",
        f"Connected components    : {n_comp:,}",
        "",
        "PRIMARY DIAGNOSTIC 1 — connected-component size",
        f"  frozen threshold      : tiny/isolated <= {TINY_PATCH_MAX_CELLS} cells",
        f"  tiny/isolated cells   : {int(tiny_suspect.sum()):,}",
        "",
        "PRIMARY DIAGNOSTIC 2 — neighbourhood-spike",
        f"  frozen window         : {SPIKE_WINDOW_SIZE}x{SPIKE_WINDOW_SIZE} (immediate 8 neighbours)",
        f"  heuristic threshold   : >= {SPIKE_DROP_M:.1f} m below local median",
        "                          (heuristic diagnostic threshold; not itself",
        "                           evidence of an artifact)",
        "  note                  : local median is computed over the full 3x3",
        "                          neighbourhood (centre included); it is used only",
        "                          as a robust local-context diagnostic, not as a",
        "                          terrain-truth reference",
        f"  spike-suspect cells   : {int(spike_suspect.sum()):,}",
        f"  edge cells excluded   : {spike_excluded_edge:,} "
        "(full 3x3 neighbourhood unavailable;",
        "                          not independently interpreted as spike evidence)",
        "",
        "COMBINED (diagnostic evidence)",
        f"  artifact-suspect      : {int(suspect.sum()):,} "
        f"({100*suspect.sum()/n_deep:.1f}% of deep)",
        f"  unflagged deep        : {int(unflagged.sum()):,} "
        f"({100*unflagged.sum()/n_deep:.1f}% of deep)",
        f"  (both diagnostics)    : {both_suspect:,} cells triggered BOTH tiny-patch and spike",
        "",
        "INTERPRETATION",
        "  'Artifact-suspect' = tiny/isolated patch and/or sharp local spike. This",
        "  RAISES suspicion of a DEM artifact but does NOT prove one; a genuine small",
        "  topographic feature can produce the same signature. Thresholds are",
        "  heuristic. Independent confirmation is deferred to V4 (flow-accumulation",
        "  cross-check). V3 answers only: which deep candidates deserve further",
        "  scrutiny? It does not remove or reclassify anything.",
        "",
        "COMPONENT-SIZE DISTRIBUTION (deep patches)",
    ]
    for k in [1, 2, 5, 10, 50]:
        lines.append(f"  components <= {k:3d} cells : {int((comp_sizes <= k).sum()):,}")
    lines.append(f"  largest component       : {int(comp_sizes.max()):,} cells")
    with open("outputs/artifact_suspect_report.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("[ok] wrote outputs/artifact_suspect_report.txt")

    # ---- static map ----
    view = np.full(tiers.shape, np.nan)
    view[unflagged] = 1
    view[suspect]   = 2
    cmap = ListedColormap(["#2c7fb8", "#d7301f"])
    norm = BoundaryNorm([0.5, 1.5, 2.5], cmap.N)
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(np.ma.masked_invalid(view), cmap=cmap, norm=norm,
              extent=extent, origin="upper", interpolation="nearest")
    handles = [
        Patch(facecolor="#2c7fb8", edgecolor="#555",
              label="Unflagged deep (connected, locally consistent)"),
        Patch(facecolor="#d7301f", edgecolor="#555",
              label="Artifact-suspect (tiny/isolated or local spike)"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.9)
    ax.set_title("Noida V3 — Deep-candidate artifact-suspect diagnostics\n"
                 "suspect = raises suspicion, NOT confirmed; flow-accumulation -> V4",
                 fontsize=11)
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.savefig("outputs/artifact_suspect_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("[ok] wrote outputs/artifact_suspect_map.png")


if __name__ == "__main__":
    main()
