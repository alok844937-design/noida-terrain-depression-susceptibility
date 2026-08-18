"""
V6-B — MAPPED DRAINAGE PROXIMITY of V4 bucket-2 depressions (descriptive only)
=============================================================================
Describes how close terrain-susceptible closed depressions (V4 bucket-2) sit to
OSM-mapped drainage features. DESCRIPTIVE PROXIMITY ONLY.

PRIMARY mapped drainage = waterway in {drain, ditch}.
Waterways {canal, stream, river} are reported SEPARATELY (NOT merged into the
drainage distance): a canal 80 m away is NOT "within 80 m of drainage".

CAVEATS (must stay in the report):
  - These are distances to OSM-MAPPED features, NOT actual drainage availability
    or network completeness.
  - Absence of a mapped drain near a cell does NOT demonstrate absence of drainage
    on the ground.
  - OSM-mapped drainage is a PARTIAL mapped network; municipal completeness unknown.

Metric A: nearest drain/ditch distance (m) from each bucket-2 cell centroid
          -> mean/median/P25/P75/P90/max.
Metric B: descriptive distance bands <=50 / <=100 / <=250 / >250 m
          (NOT risk thresholds).
Reporting: whole bucket-2 + per-4-ERA5-quadrant + SW zone highlight.

NO risk score, NO mitigation score, NO weights, NO "drain nearby = safe" /
"no drain = dangerous", NO availability/completeness claims. V6-A untouched.

Inputs : data/noida_dem_utm.tif, outputs/flow_crosscheck_evidence.tif, OSMnx
Outputs: outputs/drainage_proximity_v6b_report.txt
         outputs/drainage_proximity_v6b.json
         outputs/nearest_mapped_drain_utm.tif  (bucket-2 only, else -9999)
"""
import json
import numpy as np
import rasterio
from rasterio.warp import transform_bounds, transform as wt
from shapely.geometry import box, Point
from shapely.strtree import STRtree

DEM_UTM = "data/noida_dem_utm.tif"
EVID    = "outputs/flow_crosscheck_evidence.tif"
EXPECTED_CRS = "EPSG:32644"
BUCKET2 = 2
NODATA  = -9999.0

DRAIN_TAGS = {"drain", "ditch"}                 # PRIMARY mapped drainage
WATERWAY_TAGS = {"canal", "stream", "river"}    # separate context
ERA5 = [(28.5, 77.25), (28.5, 77.5), (28.75, 77.25), (28.75, 77.5)]
SW_CELL = (28.5, 77.25)
BANDS = [(50, "<=50m"), (100, "<=100m"), (250, "<=250m")]


def nearest_dist(points_xy, geoms):
    """Nearest distance (m) from each (x,y) to any geometry in geoms, via STRtree."""
    if len(geoms) == 0:
        return np.full(len(points_xy), np.inf)
    tree = STRtree(geoms)
    out = np.empty(len(points_xy), dtype="float64")
    for i, (x, y) in enumerate(points_xy):
        p = Point(x, y)
        idx = tree.nearest(p)
        # shapely 2.x: nearest returns an index; 1.x: returns a geometry
        g = geoms[int(idx)] if isinstance(idx, (int, np.integer)) else idx
        out[i] = p.distance(g)
    return out


def main():
    try:
        import osmnx as ox
    except Exception as e:
        print(f"[error] need osmnx: {e}")
        return
    ox.settings.use_cache = True
    ox.settings.cache_folder = "outputs/osm_cache"

    with rasterio.open(DEM_UTM) as s:
        crs = s.crs
        if crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"DEM CRS {crs} != {EXPECTED_CRS}")
        tf = s.transform; W, H = s.width, s.height
        prof = s.profile
        b = s.bounds
        w, so, e, n = transform_bounds(crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
    poly = box(w, so, e, n)

    with rasterio.open(EVID) as ev:
        evid = ev.read(1)
    b2 = (evid == BUCKET2)
    total_b2 = int(b2.sum())

    feat_fn = getattr(ox, "features_from_polygon", None) or ox.geometries_from_polygon
    ww = feat_fn(poly, {"waterway": True})
    ww = ww[ww.geometry.notnull()].to_crs(crs)
    if "waterway" not in ww:
        print("[error] no 'waterway' column"); return

    drains = [g for g, t in zip(ww.geometry, ww["waterway"])
              if str(t) in DRAIN_TAGS and g is not None and not g.is_empty]
    waters = [g for g, t in zip(ww.geometry, ww["waterway"])
              if str(t) in WATERWAY_TAGS and g is not None and not g.is_empty]
    print(f"[info] mapped drains(drain/ditch)={len(drains)}  waterways(canal/stream/river)={len(waters)}")

    # bucket-2 cell centroids (UTM)
    b2_rows, b2_cols = np.where(b2)
    xs = tf.c + (b2_cols + 0.5) * tf.a
    ys = tf.f + (b2_rows + 0.5) * tf.e
    pts = list(zip(xs.tolist(), ys.tolist()))

    d_drain = nearest_dist(pts, drains)
    d_water = nearest_dist(pts, waters)

    # ERA5 quadrant per bucket-2 cell
    lon, lat = wt(crs, "EPSG:4326", xs.tolist(), ys.tolist())
    lon = np.array(lon); lat = np.array(lat)
    d2 = [(lat - a) ** 2 + (lon - o) ** 2 for (a, o) in ERA5]
    quad = np.argmin(np.stack(d2, 0), 0)
    sw_idx = ERA5.index(SW_CELL)
    cell_km2 = abs(tf.a * tf.e) / 1e6

    def summarize(sel):
        dd = d_drain[sel]
        if dd.size == 0:
            return {"cells": 0}
        finite = dd[np.isfinite(dd)]
        r = {
            "cells": int(dd.size),
            "area_km2": round(int(dd.size) * cell_km2, 3),
            "drain_mean_m": round(float(finite.mean()), 1) if finite.size else None,
            "drain_median_m": round(float(np.median(finite)), 1) if finite.size else None,
            "drain_P25_m": round(float(np.percentile(finite, 25)), 1) if finite.size else None,
            "drain_P75_m": round(float(np.percentile(finite, 75)), 1) if finite.size else None,
            "drain_P90_m": round(float(np.percentile(finite, 90)), 1) if finite.size else None,
            "drain_max_m": round(float(finite.max()), 1) if finite.size else None,
        }
        for thr, name in BANDS:
            r[f"within_{name}"] = int((dd <= thr).sum())
            r[f"within_{name}_pct"] = round(float((dd <= thr).mean()) * 100, 1)
        r["beyond_250m"] = int((dd > 250).sum())
        r["beyond_250m_pct"] = round(float((dd > 250).mean()) * 100, 1)
        return r

    whole = summarize(np.ones(len(pts), dtype=bool))
    per_quad = {f"({a},{o})": summarize(quad == k) for k, (a, o) in enumerate(ERA5)}
    sw = summarize(quad == sw_idx)

    # nearest-drain raster (bucket-2 only)
    draster = np.full((H, W), NODATA, dtype="float32")
    for (r, c, dv) in zip(b2_rows.tolist(), b2_cols.tolist(), d_drain.tolist()):
        draster[r, c] = dv if np.isfinite(dv) else NODATA
    prof.update(dtype="float32", count=1, nodata=NODATA)
    with rasterio.open("outputs/nearest_mapped_drain_utm.tif", "w", **prof) as d:
        d.write(draster, 1)

    out = {
        "mapped_drains_drain_ditch": len(drains),
        "waterways_canal_stream_river": len(waters),
        "total_bucket2_cells": total_b2,
        "whole_bucket2": whole,
        "per_quadrant": per_quad,
        "sw_zone": sw,
        "waterway_note": "canal/stream/river reported separately; NOT drainage",
    }
    with open("outputs/drainage_proximity_v6b.json", "w") as f:
        json.dump(out, f, indent=2)

    def block(title, s):
        if s.get("cells", 0) == 0:
            return [f"{title}: (no bucket-2 cells)"]
        return [
            title,
            f"  cells={s['cells']} area={s.get('area_km2')}km2  nearest drain/ditch: "
            f"mean={s['drain_mean_m']} median={s['drain_median_m']} "
            f"P25={s['drain_P25_m']} P75={s['drain_P75_m']} P90={s['drain_P90_m']} max={s['drain_max_m']} (m)",
            f"  within <=50m={s['within_<=50m_pct']}%  <=100m={s['within_<=100m_pct']}%  "
            f"<=250m={s['within_<=250m_pct']}%  >250m={s['beyond_250m_pct']}%",
        ]

    L = [
        "NOIDA V6-B — MAPPED DRAINAGE PROXIMITY of terrain-susceptible depressions",
        "=" * 72,
        "DESCRIPTIVE proximity only. PRIMARY mapped drainage = drain + ditch.",
        "Canal/stream/river reported separately as waterways (NOT drainage).",
        "CAVEATS: distances are to OSM-MAPPED features, NOT actual drainage",
        "availability/completeness. Absence of a mapped drain != no drainage on the",
        "ground. OSM drainage is a PARTIAL mapped network; completeness unknown.",
        "NOT risk thresholds; no 'drain nearby = safe' / 'no drain = dangerous'.",
        "",
        f"OSM mapped drains (drain/ditch)         : {len(drains)}",
        f"OSM waterways (canal/stream/river)      : {len(waters)}  (separate context)",
        f"Bucket-2 cells                          : {total_b2:,}",
        "",
    ]
    L += block("WHOLE BUCKET-2", whole)
    L += ["", "PER ERA5 QUADRANT (continuity with V5/V6-A)"]
    for lab, s in per_quad.items():
        star = "  <-- SW" if lab == f"({SW_CELL[0]},{SW_CELL[1]})" else ""
        if s.get("cells", 0) == 0:
            L.append(f"  {lab}: (none)"); continue
        L.append(f"  {lab}{star}: median={s['drain_median_m']}m  "
                 f"<=100m={s['within_<=100m_pct']}%  >250m={s['beyond_250m_pct']}%")
    L += [""]
    L += block("SW SUSCEPTIBLE ZONE (28.5,77.25) — V5/V6-A focus (63% of bucket-2)", sw)
    # waterway proximity (whole bucket-2) reported separately
    wfin = d_water[np.isfinite(d_water)]
    L += [
        "",
        "SEPARATE WATERWAY PROXIMITY (canal/stream/river; whole bucket-2)",
        f"  nearest waterway: median={round(float(np.median(wfin)),1) if wfin.size else None}m "
        f"mean={round(float(wfin.mean()),1) if wfin.size else None}m "
        f"(context only; a waterway is NOT stormwater drainage)",
        "",
        "INTERPRETATION",
        "  Susceptible depressions are generally FAR from OSM-mapped drainage",
        "  (median ~767 m; ~85% beyond 250 m). CRITICAL: only ~379 mapped drains",
        "  exist for all of Noida, so this most likely reflects OSM mapped-network",
        "  SPARSITY, NOT actual drainage absence on the ground. It is NOT a statement",
        "  about real drainage adequacy or waterlogging. Ground truth needs V7.",
    ]
    with open("outputs/drainage_proximity_v6b_report.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/drainage_proximity_v6b_report.txt")
    print("[ok] wrote outputs/drainage_proximity_v6b.json")
    print("[ok] wrote outputs/nearest_mapped_drain_utm.tif")


if __name__ == "__main__":
    main()
