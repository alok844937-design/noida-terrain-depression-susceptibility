"""
V5 — RAINFALL x TERRAIN CO-LOCATION (frozen spec, MAX-6h; plausibility not risk)
==============================================================================
FROZEN SPEC:
  Scope   : V4 bucket-2 (unflagged + low-flow = closed depressions) PRIMARY;
            bucket-1 CONTEXT only; buckets 3 & 4 EXCLUDED.
  Depth   : V4 built buckets ONLY on deep (>3 m, tier-4) candidates, so bucket-2
            is deep-only BY CONSTRUCTION (verified 8026/8026 tier-4). Depth
            sub-split not applicable -> omitted.
  Flow/TWI: no TWI; low-flow bucket membership IS the flow evidence.
  Join    : each DEM cell -> NEAREST of 4 ERA5 cells (coarse ~25km ASSIGNMENT,
            NOT forcing attribution).
  Forcing : per event, strongest coarse cell = highest event MAX rolling-6h
            (coherent with frozen V5 event-ranking). Total-based retained in
            JSON for audit only.
  Intersect: COUNT + conditional-AREA. NO multiplied risk score. NO re-ranking.
  Wording : "coarse ERA5 cell assignment"; "susceptible-area co-location with the
            strongest coarse forcing" (never "exposure"/"risk").
Inputs : outputs/flow_crosscheck_evidence.tif, outputs/percell_event_metrics.json
Outputs: outputs/fusion_v5_report.txt, outputs/fusion_v5.json
"""
import json
import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

EVID   = "outputs/flow_crosscheck_evidence.tif"
PCJSON = "outputs/percell_event_metrics.json"
EXPECTED_CRS = "EPSG:32644"
NODATA = -9999.0
BUCKET2, BUCKET1 = 2, 1


def load(path):
    with rasterio.open(path) as s:
        if s.crs is None or s.crs.to_string() != EXPECTED_CRS:
            raise ValueError(f"{path}: expected {EXPECTED_CRS}, found {s.crs}")
        return s.read(1).astype("float64"), s.transform, s.width, s.height, s.crs


def main():
    evid, tf, W, H, crs = load(EVID)
    with open(PCJSON) as f:
        pc = json.load(f)
    labs = pc["cells"]
    events = pc["events"]

    def parse(lab):
        a, b = lab.strip("()").split(",")
        return float(a), float(b)
    era5 = {lab: parse(lab) for lab in labs}

    rows, cols = np.mgrid[0:H, 0:W]
    xs = tf.c + (cols + 0.5) * tf.a + (rows + 0.5) * tf.b
    ys = tf.f + (cols + 0.5) * tf.d + (rows + 0.5) * tf.e
    lon, lat = warp_transform(crs, "EPSG:4326", xs.ravel(), ys.ravel())
    lon = np.array(lon).reshape(H, W); lat = np.array(lat).reshape(H, W)
    d2 = [(lat - era5[l][0])**2 + (lon - era5[l][1])**2 for l in labs]
    nearest = np.argmin(np.stack(d2, 0), 0)

    b2 = (evid == BUCKET2); b1 = (evid == BUCKET1)
    cell_km2 = abs(tf.a * tf.e) / 1e6
    total_b2 = int(b2.sum())

    percell_static = {}
    for k, lab in enumerate(labs):
        m = (nearest == k)
        percell_static[lab] = {
            "b2_cells": int((b2 & m).sum()),
            "b2_area_km2": round(float((b2 & m).sum() * cell_km2), 3),
            "b1_context_cells": int((b1 & m).sum()),
        }

    ev_out = []
    for e in events:
        rain = {l: {"total_mm": e["percell"].get(l, {}).get("total_mm"),
                    "max_6h_mm": e["percell"].get(l, {}).get("max_6h_mm")} for l in labs}
        strongest6 = max(labs, key=lambda L: rain[L]["max_6h_mm"])
        strongestT = max(labs, key=lambda L: rain[L]["total_mm"])
        ev_out.append({
            "rank": e["rank"], "start": e["start"],
            "strongest_cell_max6": strongest6,
            "strongest_max6_mm": rain[strongest6]["max_6h_mm"],
            "strongest_total_mm_at_that_cell": rain[strongest6]["total_mm"],
            "b2_cells_colocated": percell_static[strongest6]["b2_cells"],
            "b2_area_colocated_km2": percell_static[strongest6]["b2_area_km2"],
            "_audit_strongest_cell_total": strongestT,
            "_audit_total_vs_max6_differ": strongestT != strongest6,
            "cell_rain": rain,
        })

    out = {
        "spec": "MAX-6h strongest forcing; bucket-2 primary (deep-only by V4 "
                "construction); bucket-1 context; 3&4 excluded; count+area; coarse "
                "ERA5 assignment; no risk score; no re-ranking",
        "total_bucket2_cells": total_b2,
        "total_bucket2_area_km2": round(total_b2 * cell_km2, 3),
        "percell_static": percell_static,
        "events": ev_out,
    }
    with open("outputs/fusion_v5.json", "w") as f:
        json.dump(out, f, indent=2)

    n_diff = sum(1 for e in ev_out if e["_audit_total_vs_max6_differ"])
    L = [
        "NOIDA V5 — RAINFALL x TERRAIN CO-LOCATION (frozen spec; MAX-6h)",
        "=" * 70,
        "Scope: V4 bucket-2 (closed depressions) PRIMARY; bucket-1 CONTEXT; 3&4 excluded.",
        "Depth: bucket-2 is deep-only (>3m) BY V4 CONSTRUCTION (8026/8026 tier-4);",
        "       a depth sub-split is not applicable and is omitted.",
        "Forcing: strongest coarse cell = highest event MAX rolling-6h (coherent with",
        "       the frozen V5 event-ranking metric). Coarse ~25km ASSIGNMENT, NOT",
        "       forcing attribution. COUNT + conditional-AREA. No risk score, no re-ranking.",
        "",
        f"Total bucket-2 cells        : {total_b2:,} ({out['total_bucket2_area_km2']} km2)",
        f"(total-based vs max6-based strongest differ in {n_diff}/10 events; max6 is frozen)",
        "",
        "BUCKET-2 SUSCEPTIBLE AREA PER COARSE ERA5 CELL (static assignment)",
    ]
    for lab in labs:
        s = percell_static[lab]
        L.append(f"  {lab:16s}: b2={s['b2_cells']:>5} ({s['b2_area_km2']:>6.2f} km2)  "
                 f"b1-context={s['b1_context_cells']}")
    L += ["",
          "PER-EVENT: SUSCEPTIBLE-AREA CO-LOCATION WITH STRONGEST COARSE FORCING (MAX-6h)"]
    for e in ev_out:
        flag = "  [total-strongest differs]" if e["_audit_total_vs_max6_differ"] else ""
        L.append(f"  [{e['rank']:>2}] {e['start']:16s}  strongest(max6)={e['strongest_cell_max6']} "
                 f"(6h={e['strongest_max6_mm']:.1f}mm)  b2 co-located="
                 f"{e['b2_cells_colocated']} ({e['b2_area_colocated_km2']:.2f} km2){flag}")
    L += [
        "",
        "INTERPRETATION",
        "  Reports where V4-identified terrain-susceptible closed depressions spatially",
        "  CO-LOCATE with the strongest coarse ERA5 forcing (max-6h) during frozen",
        "  events. NOT observed waterlogging, NOT a risk score; rainfall NOT resolved",
        "  to 30 m; 'strongest coarse cell' is a ~25 km assignment. Confirmation needs",
        "  observed data (V7) and urban context (V6).",
    ]
    with open("outputs/fusion_v5_report.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/fusion_v5_report.txt")
    print("[ok] wrote outputs/fusion_v5.json")


if __name__ == "__main__":
    main()
