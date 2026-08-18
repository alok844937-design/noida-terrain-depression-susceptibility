"""
V6-A — URBAN CONTEXT CHARACTERIZATION of V4 bucket-2 closed depressions
======================================================================
Characterizes the BUILT/TRANSPORT context of terrain-susceptible closed
depressions (V4 bucket-2). PRIMARY = building coverage fraction per 30 m cell
(continuous). SECONDARY = road length per cell, land-use context.

INTERPRETATION LOCK: this CHARACTERIZES context; it does NOT assign a causal
risk direction. A building footprint intersecting a depression is a spatial
fact; whether/why it changes waterlogging is unresolved (-> V7). NO risk score,
NO weights, NO "built-up = higher risk", NO imperviousness claim from buildings.

Method (coverage fraction, continuous):
  - reproject OSM buildings to DEM CRS (UTM 44N)
  - rasterize building footprints at a FINE subgrid (~3 m), value=1
  - block-average the fine grid down to the 30 m DEM grid -> coverage fraction
    in [0,1] per DEM cell (retains fractional info; no premature binarization)
  - restrict to bucket-2 cells; aggregate whole + per ERA5 quadrant + SW zone

Roads: rasterize road lines at fine subgrid, sum intersecting length per 30 m
  cell (approx via fine-cell count x fine-res). Reported as length density.

Inputs:
  data/noida_dem_utm.tif                (grid + CRS reference)
  outputs/flow_crosscheck_evidence.tif  (V4 buckets; bucket-2)
  OSM via OSMnx (buildings, roads, landuse) over DEM bbox
Outputs:
  outputs/urban_context_v6a_report.txt
  outputs/urban_context_v6a.json
  outputs/building_coverage_utm.tif     (coverage fraction raster, bucket-2 only)
"""
import json
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.features import rasterize
from shapely.geometry import box
from shapely.geometry import box as sbox
from shapely.strtree import STRtree

DEM_UTM = "data/noida_dem_utm.tif"
EVID    = "outputs/flow_crosscheck_evidence.tif"
EXPECTED_CRS = "EPSG:32644"
BUCKET2 = 2
SUBGRID = 10   # fine cells per DEM cell per axis -> ~2.9 m subgrid (10x10=100 subcells)

# the 4 ERA5 cells (lat,lon) used in V5; SW is (28.5,77.25)
ERA5 = [(28.5, 77.25), (28.5, 77.5), (28.75, 77.25), (28.75, 77.5)]
SW_CELL = (28.5, 77.25)


def main():
    try:
        import osmnx as ox
        import geopandas as gpd
    except Exception as e:
        print(f"[error] need osmnx+geopandas: {e}")
        return

    ox.settings.use_cache = True
    ox.settings.cache_folder = "outputs/osm_cache"

    with rasterio.open(DEM_UTM) as s:
        crs = s.crs
        if crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"DEM CRS {crs} != {EXPECTED_CRS}")
        tf = s.transform; W, H = s.width, s.height
        b = s.bounds
        w, so, e, n = transform_bounds(crs, "EPSG:4326", b.left, b.bottom, b.right, b.top)
    poly = box(w, so, e, n)

    with rasterio.open(EVID) as ev:
        evid = ev.read(1)
    b2 = (evid == BUCKET2)
    total_b2 = int(b2.sum())

    feat_fn = getattr(ox, "features_from_polygon", None) or ox.geometries_from_polygon

    # ---- buildings -> UTM ----
    print("[info] fetching buildings...")
    bld = feat_fn(poly, {"building": True})
    bld = bld[bld.geometry.type.isin(["Polygon", "MultiPolygon"])].to_crs(crs)

    # fine subgrid transform (SUBGRID x finer)
    fine_tf = rasterio.Affine(tf.a / SUBGRID, tf.b, tf.c,
                              tf.d, tf.e / SUBGRID, tf.f)
    fine_W, fine_H = W * SUBGRID, H * SUBGRID

    print("[info] rasterizing buildings at fine subgrid...")
    bshapes = ((geom, 1) for geom in bld.geometry if geom is not None and not geom.is_empty)
    fine_bld = rasterize(bshapes, out_shape=(fine_H, fine_W), transform=fine_tf,
                         fill=0, dtype="uint8", all_touched=False)
    # block-average down to 30 m -> coverage fraction
    cov = fine_bld.reshape(H, SUBGRID, W, SUBGRID).mean(axis=(1, 3)).astype("float64")

    # ---- roads -> UTM; EXACT clipped length (m) per bucket-2 cell (vector) ----
    print("[info] fetching roads...")
    rd = feat_fn(poly, {"highway": True})
    rd = rd[rd.geometry.type.isin(["LineString", "MultiLineString"])].to_crs(crs)
    road_geoms = [g for g in rd.geometry if g is not None and not g.is_empty]
    tree = STRtree(road_geoms)
    rd_len = np.zeros((H, W), dtype="float64")
    b2_rows, b2_cols = np.where(b2)
    for r, c in zip(b2_rows.tolist(), b2_cols.tolist()):
        x0 = tf.c + c * tf.a
        y0 = tf.f + r * tf.e
        cell = sbox(min(x0, x0 + tf.a), min(y0, y0 + tf.e),
                    max(x0, x0 + tf.a), max(y0, y0 + tf.e))
        hits = tree.query(cell)
        if len(hits) == 0:
            continue
        Lsum = 0.0
        for h in hits:
            # shapely 2.x: query returns int indices; 1.x: returns geometries
            g = road_geoms[int(h)] if np.issubdtype(type(h), np.integer) or isinstance(h, (int, np.integer)) else h
            inter = g.intersection(cell)
            if not inter.is_empty:
                Lsum += inter.length
        rd_len[r, c] = Lsum

    # ---- DEM cell -> nearest ERA5 quadrant (for SW highlight & per-quadrant) ----
    rows, cols = np.mgrid[0:H, 0:W]
    xs = tf.c + (cols + 0.5) * tf.a
    ys = tf.f + (rows + 0.5) * tf.e
    from rasterio.warp import transform as wt
    lon, lat = wt(crs, "EPSG:4326", xs.ravel(), ys.ravel())
    lon = np.array(lon).reshape(H, W); lat = np.array(lat).reshape(H, W)
    d2 = [(lat - a) ** 2 + (lon - o) ** 2 for (a, o) in ERA5]
    nearest = np.argmin(np.stack(d2, 0), 0)
    sw_idx = ERA5.index(SW_CELL)

    cell_km2 = abs(tf.a * tf.e) / 1e6

    def summarize(mask):
        m = b2 & mask
        n = int(m.sum())
        if n == 0:
            return {"cells": 0}
        c = cov[m]
        bands = {
            "0%": int((c == 0).sum()),
            "0-25%": int(((c > 0) & (c <= 0.25)).sum()),
            "25-50%": int(((c > 0.25) & (c <= 0.5)).sum()),
            "50-75%": int(((c > 0.5) & (c <= 0.75)).sum()),
            "75-100%": int((c > 0.75).sum()),
        }
        return {
            "cells": n,
            "area_km2": round(n * cell_km2, 3),
            "cov_mean": round(float(c.mean()), 4),
            "cov_median": round(float(np.median(c)), 4),
            "pct_area_any_building": round(float((c > 0).mean()) * 100, 1),
            "coverage_bands": bands,
            "road_len_m_mean": round(float(rd_len[m].mean()), 1),
            "road_len_m_per_km2": round(float(rd_len[m].sum() / (n * cell_km2)), 1),
        }

    whole = summarize(np.ones_like(b2, dtype=bool))
    per_quad = {}
    for k, (a, o) in enumerate(ERA5):
        per_quad[f"({a},{o})"] = summarize(nearest == k)
    sw = summarize(nearest == sw_idx)

    # ---- land-use context (audit-style counts within bucket-2 bbox) ----
    print("[info] fetching land-use...")
    try:
        lu = feat_fn(poly, {"landuse": True})
        lu_counts = lu["landuse"].value_counts().head(12).to_dict() if len(lu) else {}
        lu_counts = {str(k): int(v) for k, v in lu_counts.items()}
    except Exception as ex:
        lu_counts = {"error": str(ex)[:40]}

    # ---- save coverage raster (bucket-2 only) ----
    cov_out = np.where(b2, cov, -9999.0).astype("float32")
    with rasterio.open(DEM_UTM) as s:
        prof = s.profile
    prof.update(dtype="float32", count=1, nodata=-9999.0)
    with rasterio.open("outputs/building_coverage_utm.tif", "w", **prof) as d:
        d.write(cov_out, 1)

    out = {
        "total_bucket2_cells": total_b2,
        "n_buildings": int(len(bld)),
        "n_roads": int(len(rd)),
        "whole_bucket2": whole,
        "per_quadrant": per_quad,
        "sw_zone": sw,
        "landuse_context_counts": lu_counts,
        "note": "characterization only; no risk direction; buildings != imperviousness",
    }
    with open("outputs/urban_context_v6a.json", "w") as f:
        json.dump(out, f, indent=2)

    L = [
        "NOIDA V6-A — URBAN CONTEXT OF TERRAIN-SUSCEPTIBLE DEPRESSIONS (bucket-2)",
        "=" * 72,
        "Characterizes built/transport context. Does NOT assign a causal risk",
        "direction. Building coverage = spatial fact; buildings != measured",
        "imperviousness. No risk score, no weights, no observed-waterlogging claim.",
        f"OSM: {len(bld):,} building footprint geometries, {len(rd):,} road lines.",
        f"Bucket-2 total: {total_b2:,} cells.",
        "",
        "WHOLE BUCKET-2",
        f"  building coverage mean={whole['cov_mean']} median={whole['cov_median']}  "
        f"%area with any building={whole['pct_area_any_building']}%",
        f"  coverage bands: {whole['coverage_bands']}",
        f"  road length: mean={whole['road_len_m_mean']} m/cell, "
        f"{whole['road_len_m_per_km2']} m/km2",
        "",
        "PER ERA5 QUADRANT (continuity with V5)",
    ]
    for lab, s in per_quad.items():
        if s.get("cells", 0) == 0:
            L.append(f"  {lab:16s}: (no bucket-2 cells)")
            continue
        star = "  <-- SW HIGHLIGHT" if lab == f"({SW_CELL[0]},{SW_CELL[1]})" else ""
        L.append(f"  {lab:16s}: cells={s['cells']:>5} cov_mean={s['cov_mean']:.3f} "
                 f"any={s['pct_area_any_building']:.0f}% road={s['road_len_m_per_km2']:.0f}m/km2{star}")
    L += [
        "",
        "SW SUSCEPTIBLE ZONE (28.5,77.25) — V5 focus (63% of bucket-2)",
        f"  cells={sw['cells']}  area={sw.get('area_km2')} km2",
        f"  building coverage mean={sw['cov_mean']} median={sw['cov_median']}  "
        f"%area any building={sw['pct_area_any_building']}%",
        f"  coverage bands: {sw['coverage_bands']}",
        f"  road length: {sw['road_len_m_per_km2']} m/km2",
        "",
        f"LAND-USE CONTEXT (bbox counts): {lu_counts}",
        "",
        "INTERPRETATION",
        "  These are contextual facts about where terrain-susceptible closed",
        "  depressions sit relative to OSM-mapped buildings/roads/land-use. No causal",
        "  risk direction is assigned (a built-up depression may be more OR less prone",
        "  to ponding — unresolved here). Confirmation requires observed data (V7).",
    ]
    with open("outputs/urban_context_v6a_report.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/urban_context_v6a_report.txt")
    print("[ok] wrote outputs/urban_context_v6a.json")
    print("[ok] wrote outputs/building_coverage_utm.tif")


if __name__ == "__main__":
    main()
