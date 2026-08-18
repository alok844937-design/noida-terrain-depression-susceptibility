"""
V6-Audit — OSM URBAN-CONTEXT AVAILABILITY AUDIT (audit only)
===========================================================
Determines what urban-context and drainage information is actually available in
OpenStreetMap over the Noida study area BEFORE any susceptibility refinement.
Counts features, geometry types, coverage; performs an audit-only overlap check
against V4 bucket-2 closed depressions.

NO fusion. NO susceptibility modification. NO risk score. V4/V5 untouched.

Methodological safeguards:
  - OSM buildings/roads are BUILT/TRANSPORT CONTEXT, a proxy — NOT "impervious
    surface percentage" (that needs a real land-cover dataset).
  - Missing OSM drainage != no drainage on the ground. If drains are sparsely
    mapped, the audit says the OSM drainage representation is insufficient for a
    defensible constraint analysis — it does not fabricate drainage.

Study area: DEM bbox (read from data/noida_dem_utm.tif -> WGS84 polygon).
Access    : OSMnx (Overpass). Respect rate limits; no mass/parallel queries.

Outputs:
  outputs/osm_audit_report.txt
  outputs/osm_audit_raw.json
  outputs/osm_cache/  (OSMnx cache, if enabled)
"""
import json
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import box

DEM_UTM = "data/noida_dem_utm.tif"
EVID    = "outputs/flow_crosscheck_evidence.tif"
BUCKET2 = 2

# OSM tag groups to audit (availability only)
TAG_QUERIES = {
    "buildings":  {"building": True},
    "roads":      {"highway": True},
    "landuse":    {"landuse": True},
    "waterways":  {"waterway": True},   # includes river/stream/canal/drain/ditch
}
# drainage-specific waterway subtypes we care about (audited from waterways set)
DRAIN_SUBTYPES = {"drain", "ditch", "canal", "stream"}


def study_polygon():
    with rasterio.open(DEM_UTM) as s:
        b = s.bounds
        w, so, e, n = transform_bounds(s.crs, "EPSG:4326",
                                       b.left, b.bottom, b.right, b.top)
    return box(w, so, e, n), (w, so, e, n)


def geom_summary(gdf):
    """Count by geometry type; total length (deg) for lines; count for polys."""
    if gdf is None or len(gdf) == 0:
        return {"count": 0}
    types = gdf.geometry.type.value_counts().to_dict()
    out = {"count": int(len(gdf)), "geom_types": {k: int(v) for k, v in types.items()}}
    return out


def main():
    try:
        import osmnx as ox
    except Exception as e:
        print(f"[error] osmnx not importable: {e}")
        print("        run: pip install osmnx")
        return

    ox.settings.use_cache = True
    ox.settings.cache_folder = "outputs/osm_cache"
    ox.settings.log_console = False

    poly, bbox = study_polygon()
    print(f"[info] study bbox WSEN: {tuple(round(x,4) for x in bbox)}")

    # version-safe features_from_polygon
    feat_fn = getattr(ox, "features_from_polygon", None)
    if feat_fn is None:
        feat_fn = ox.geometries_from_polygon  # older osmnx

    raw = {}
    summary = {}
    for name, tags in TAG_QUERIES.items():
        try:
            gdf = feat_fn(poly, tags)
        except Exception as ex:
            print(f"[warn] query '{name}' failed/empty: {ex}")
            summary[name] = {"count": 0, "error": str(ex)}
            continue
        s = geom_summary(gdf)
        # extra per-layer detail
        if name == "landuse" and len(gdf):
            vc = gdf["landuse"].value_counts().head(15).to_dict() if "landuse" in gdf else {}
            s["top_landuse"] = {str(k): int(v) for k, v in vc.items()}
        if name == "waterways" and len(gdf) and "waterway" in gdf:
            wv = gdf["waterway"].value_counts().to_dict()
            s["waterway_subtypes"] = {str(k): int(v) for k, v in wv.items()}
            s["drainage_related"] = int(sum(int(v) for k, v in wv.items()
                                            if str(k) in DRAIN_SUBTYPES))
        summary[name] = s
        raw[name] = {"count": int(len(gdf))}

    # ---- audit-only overlap: bucket-2 vs building footprints ----
    overlap_note = "not computed"
    try:
        with rasterio.open(EVID) as ev:
            evid = ev.read(1)
            b2_total = int((evid == BUCKET2).sum())
        overlap_note = (f"bucket-2 total cells = {b2_total:,}. Spatial overlap with OSM "
                        "buildings is deferred to V6 analysis (audit only here).")
    except Exception as ex:
        overlap_note = f"bucket-2 raster not read: {ex}"

    with open("outputs/osm_audit_raw.json", "w") as f:
        json.dump({"bbox_WSEN": bbox, "summary": summary}, f, indent=2)

    # ---- report ----
    L = [
        "NOIDA V6-AUDIT — OSM URBAN-CONTEXT AVAILABILITY (audit only)",
        "=" * 64,
        "Access: OSMnx (Overpass). Availability/coverage only; NO fusion, NO",
        "        susceptibility change, NO risk score. V4/V5 untouched.",
        "Safeguards: OSM buildings/roads = built/transport CONTEXT proxy, NOT",
        "        'impervious surface %'. Missing OSM drainage != no drainage on ground.",
        f"Study bbox (W,S,E,N): {tuple(round(x,4) for x in bbox)}",
        "",
        "LAYER AVAILABILITY",
    ]
    for name in TAG_QUERIES:
        s = summary.get(name, {})
        if "error" in s:
            L.append(f"  {name:10s}: ERROR/empty ({s.get('error','')[:40]})")
            continue
        L.append(f"  {name:10s}: count={s.get('count',0):,}  geom={s.get('geom_types',{})}")
        if name == "landuse" and s.get("top_landuse"):
            L.append(f"              top land-use: {s['top_landuse']}")
        if name == "waterways":
            L.append(f"              waterway subtypes: {s.get('waterway_subtypes',{})}")
            L.append(f"              drainage-related (drain/ditch/canal/stream): "
                     f"{s.get('drainage_related',0)}")
    L += [
        "",
        "BUCKET-2 OVERLAP (audit note)",
        f"  {overlap_note}",
        "",
        "PROVISIONAL READING (not a decision)",
        "  Role A (built/transport context) is viable if buildings + roads are well",
        "  mapped. Role B (drainage constraint) is viable ONLY if drainage-related",
        "  waterways are sufficiently mapped; a low/zero drainage count means OSM",
        "  drainage is insufficient for a defensible constraint analysis (a data gap,",
        "  NOT evidence of absent drainage on the ground). Role decision follows this",
        "  audit; no urban modifier or risk score is defined here.",
    ]
    with open("outputs/osm_audit_report.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/osm_audit_report.txt")
    print("[ok] wrote outputs/osm_audit_raw.json")


if __name__ == "__main__":
    main()
