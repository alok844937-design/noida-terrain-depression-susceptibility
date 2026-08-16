"""
V2.1.1 — Noida Terrain-Depression Susceptibility (candidate tiers)  [FROZEN]
===========================================================================
Input  : outputs/depression_depth_utm.tif  (UTM 44N; from upstream
         depression-analysis step, depression depth = filled - original DEM).
IMPORTANT: terrain-depression CANDIDATES, NOT confirmed waterlogging.
           A deep depression is NOT assumed to be a channel (needs
           independent flow-accumulation / drainage evidence).

Outputs (outputs/):
    candidate_depressions.tif              tier raster (UTM 44N, nodata=-9999)
    candidate_depressions_methodology.txt  methodology / metadata sidecar
    depression_tier_map.png                static figure (report-quality)
    depression_tier_map.html               interactive Folium map (legend)
"""
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
import folium

DEPR_UTM     = "outputs/depression_depth_utm.tif"
EXPECTED_CRS = "EPSG:32644"
NODATA       = -9999.0

# tier code -> (label, hex color). code 0 = background / non-candidate.
TIER_META = {
    0: ("background / non-candidate",               "#00000000"),
    1: ("Minor candidate (0.2-0.5 m)",              "#fee391"),
    2: ("High candidate (0.5-2.0 m)",               "#fe9929"),
    3: ("Deep transition (2-3 m)",                  "#cc4c02"),
    4: ("Deep terrain-depression candidate (>3 m)", "#6a51a3"),
}


def classify(depr, valid):
    """depth (m) -> tier code 0..4. Explicit thresholds = transparent behavior."""
    out = np.zeros(depr.shape, dtype="float32")
    out[(depr >= 0.2) & (depr < 0.5)] = 1
    out[(depr >= 0.5) & (depr < 2.0)] = 2
    out[(depr >= 2.0) & (depr < 3.0)] = 3
    out[depr >= 3.0]                  = 4
    out[~valid] = NODATA               # invalid ko nodata; tier 0 se semantically alag
    return out


def reproject_raster(src_path, dst_path, dst_crs, resampling):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        meta = src.meta.copy()
        meta.update(crs=dst_crs, transform=transform, width=width, height=height)
        with rasterio.open(dst_path, "w", **meta) as dst:
            for i in range(1, src.count + 1):
                reproject(source=rasterio.band(src, i),
                          destination=rasterio.band(dst, i),
                          src_transform=src.transform, src_crs=src.crs,
                          dst_transform=transform, dst_crs=dst_crs,
                          resampling=resampling)
    return dst_path


def write_methodology(path, counts, cell_area_km2, res):
    lines = [
        "NOIDA TERRAIN-DEPRESSION SUSCEPTIBILITY — methodology / metadata",
        "=" * 64,
        "Source DEM      : Copernicus GLO-30 (OpenTopography)",
        "Analysis CRS    : UTM Zone 44N (EPSG:32644)",
        f"Resolution      : {res[0]:.3f} x {res[1]:.3f} m",
        "Input variable  : DEM-derived depression depth raster",
        "                  (provided by upstream depression-analysis step;",
        "                   depression depth = filled DEM - original DEM)",
        "Candidate thresh: >= 0.2 m",
        "",
        "Classification:",
        "  0.2-0.5 m  -> Minor candidate",
        "  0.5-2.0 m  -> High candidate",
        "  2.0-3.0 m  -> Deep transition",
        "  >3.0 m     -> Deep terrain-depression candidate",
        "",
        "Interpretation:",
        "  These are terrain-depression susceptibility candidates,",
        "  NOT confirmed waterlogging locations.",
        "  A deep depression is NOT assumed to be a channel; that requires",
        "  independent flow-accumulation / drainage evidence.",
        "  No drainage observations were fabricated or inferred as observed",
        "  data where unavailable.",
        "",
        "Area per tier:",
    ]
    for code in range(5):
        label = TIER_META[code][0]
        n = counts.get(code, 0)
        lines.append(f"  [{code}] {label:42s}: {n:9,} cells = {n*cell_area_km2:7.2f} km2")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[ok] wrote {path}")


def main():
    with rasterio.open(DEPR_UTM) as src:
        if src.crs is None:
            raise ValueError("Input raster has no CRS.")
        if src.crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"Expected {EXPECTED_CRS}, but found {src.crs}")
        depr = src.read(1).astype("float64")
        profile = src.profile
        b = src.bounds
        res = src.res
        nod = src.nodata
    if not np.isclose(res[0], res[1], rtol=0.01):
        print("[warning] Pixel dimensions are not approximately square.")

    # valid mask: finite, not nodata, and non-negative (negative depth = artifact)
    valid = (
        np.isfinite(depr)
        & (depr != (nod if nod is not None else NODATA))
        & (depr >= 0)
    )
    depr_v = np.where(valid, depr, np.nan)
    tiers = classify(np.nan_to_num(depr_v, nan=-1.0), valid)

    # ---- save tier raster (UTM, nodata=-9999 for GDAL/QGIS safety) ----
    profile.update(dtype="float32", count=1, nodata=NODATA)
    with rasterio.open("outputs/candidate_depressions.tif", "w", **profile) as dst:
        dst.write(tiers.astype("float32"), 1)
    print("[ok] wrote outputs/candidate_depressions.tif")

    # ---- methodology sidecar ----
    counts = {code: int((tiers == code).sum()) for code in range(5)}
    write_methodology("outputs/candidate_depressions_methodology.txt",
                      counts, (res[0] * res[1]) / 1e6, res)

    # ---- plotting (mask nodata so it doesn't render as a tier) ----
    tiers_plot = np.ma.masked_where(tiers == NODATA, tiers)
    colors = [TIER_META[c][1] for c in range(5)]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(list(range(6)), cmap.N)

    extent = [b.left, b.right, b.bottom, b.top]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(tiers_plot, cmap=cmap, norm=norm, extent=extent,
              origin="upper", interpolation="nearest")
    handles = [Patch(facecolor=TIER_META[c][1], edgecolor="#555",
                     label=TIER_META[c][0]) for c in range(1, 5)]
    ax.legend(handles=handles, loc="lower right", fontsize=8,
              framealpha=0.9, title="Candidate tiers")
    ax.set_title("Noida — Terrain-Depression Susceptibility (candidate tiers)\n"
                 "Copernicus GLO-30, UTM 44N  |  candidates, NOT confirmed waterlogging",
                 fontsize=11)
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.savefig("outputs/depression_tier_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("[ok] wrote outputs/depression_tier_map.png")

    # ---- RGBA (UTM) -> reproject viz to WGS84 -> Folium ----
    rgba = np.zeros((tiers.shape[0], tiers.shape[1], 4), dtype="uint8")
    for code in range(1, 5):
        hexc = TIER_META[code][1]
        r, g, bl = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
        rgba[tiers == code] = [r, g, bl, 210]
    with rasterio.open("outputs/viz_tier_utm.tif", "w",
                       **{**profile, "count": 4, "dtype": "uint8", "nodata": None}) as dst:
        for i in range(4):
            dst.write(rgba[..., i], i + 1)
    reproject_raster("outputs/viz_tier_utm.tif", "outputs/viz_tier_wgs84.tif",
                     "EPSG:4326", Resampling.nearest)

    with rasterio.open("outputs/viz_tier_wgs84.tif") as v:
        img = np.transpose(v.read(), (1, 2, 0))
        vb = v.bounds
    plt.imsave("outputs/tier_overlay.png", img)
    bounds = [[vb.bottom, vb.left], [vb.top, vb.right]]
    center = [(vb.bottom + vb.top) / 2, (vb.left + vb.right) / 2]

    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")
    folium.raster_layers.ImageOverlay(
        image="outputs/tier_overlay.png", bounds=bounds,
        opacity=0.8, name="Terrain-depression candidates").add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
        background: white; padding: 10px 12px; border:1px solid #999;
        border-radius:6px; font-size:12px; font-family:sans-serif;">
    <b>Terrain-depression candidate</b><br>
    <i style="color:#666">candidates, NOT confirmed waterlogging</i><br>
    <span style="color:#fee391">&#9632;</span> Minor (0.2-0.5 m)<br>
    <span style="color:#fe9929">&#9632;</span> High (0.5-2.0 m)<br>
    <span style="color:#cc4c02">&#9632;</span> Deep transition (2-3 m)<br>
    <span style="color:#6a51a3">&#9632;</span> Deep terrain-depression (&gt;3 m)
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))
    folium.LayerControl().add_to(m)
    m.save("outputs/depression_tier_map.html")
    print("[ok] wrote outputs/depression_tier_map.html")


if __name__ == "__main__":
    main()
