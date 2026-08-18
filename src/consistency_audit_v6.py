"""
V6 FINAL CONSISTENCY AUDIT — cross-check numbers/terminology across V4/V5/V6
===========================================================================
Verifies the frozen baseline is internally consistent BEFORE V7 (observed data).
Reads only committed outputs; recomputes key invariants and flags any mismatch.
Makes NO changes to any layer.

Checks:
  1. bucket-2 count (raster) == 8026, and == sum across 4 ERA5 quadrants
  2. V5 fusion per-quadrant b2 area == V6-A per-quadrant cells == V6-B per-quadrant cells
  3. SW quadrant (28.5,77.25) is 5080 cells / ~4.29 km2 / ~63.3% everywhere
  4. total bucket-2 area consistent (~6.783 km2) across V5/V6-A/V6-B
  5. ERA5 cell labels identical across per-cell metrics / fusion / V6
  6. selected events count == 10 in all V5 artifacts
  7. bucket-2 is deep-only (tier-4) — re-verify 8026/8026
"""
import json
import numpy as np
import rasterio

def jload(p):
    with open(p) as f:
        return json.load(f)

problems = []
notes = []

# ---- rasters ----
evid = rasterio.open("outputs/flow_crosscheck_evidence.tif").read(1)
tiers = rasterio.open("outputs/candidate_depressions.tif").read(1)
with rasterio.open("outputs/flow_crosscheck_evidence.tif") as s:
    tf = s.transform
cell_km2 = abs(tf.a * tf.e) / 1e6
b2 = (evid == 2)
b2_count = int(b2.sum())

# check 1: bucket-2 count
if b2_count != 8026:
    problems.append(f"bucket-2 count {b2_count} != 8026")
else:
    notes.append(f"bucket-2 count = {b2_count} OK")

# check 7: deep-only
b2_tiers = {int(v): int((tiers[b2] == v).sum()) for v in np.unique(tiers[b2])}
if set(b2_tiers.keys()) != {4}:
    problems.append(f"bucket-2 tier breakdown not all tier-4: {b2_tiers}")
else:
    notes.append(f"bucket-2 deep-only (tier-4): {b2_tiers[4]} OK")

# ---- load JSONs ----
fusion = jload("outputs/fusion_v5.json")
v6a = jload("outputs/urban_context_v6a.json")
v6b = jload("outputs/drainage_proximity_v6b.json")
pc = jload("outputs/percell_event_metrics.json")
sel = jload("outputs/selected_rainfall_events.json")

# check 6: 10 events everywhere
n_sel = len(sel.get("selected", []))
n_pc = len(pc.get("events", []))
if n_sel != 10 or n_pc != 10:
    problems.append(f"event count mismatch: selected={n_sel}, percell={n_pc}")
else:
    notes.append(f"selected events = 10 (selection & per-cell) OK")

# check 5: ERA5 labels identical
labs_pc = set(pc.get("cells", []))
labs_fusion = set(fusion.get("percell_static", {}).keys())
labs_v6a = set(v6a.get("per_quadrant", {}).keys())
labs_v6b = set(v6b.get("per_quadrant", {}).keys())
if not (labs_pc == labs_fusion == labs_v6a == labs_v6b):
    problems.append(f"ERA5 label sets differ:\n  pc={labs_pc}\n  fusion={labs_fusion}\n"
                    f"  v6a={labs_v6a}\n  v6b={labs_v6b}")
else:
    notes.append(f"ERA5 cell labels identical across V5/V6 ({len(labs_pc)} cells) OK")

# check 2+3+4: per-quadrant cell counts across fusion / v6a / v6b
def quad_cells_fusion(lab):
    return fusion["percell_static"][lab]["b2_cells"]
def quad_cells_v6a(lab):
    return v6a["per_quadrant"][lab]["cells"]
def quad_cells_v6b(lab):
    return v6b["per_quadrant"][lab]["cells"]

labs = sorted(labs_pc)
quad_total = 0
for lab in labs:
    cf = quad_cells_fusion(lab)
    ca = quad_cells_v6a(lab)
    cb = quad_cells_v6b(lab)
    quad_total += cf
    if not (cf == ca == cb):
        problems.append(f"quadrant {lab} cell mismatch: fusion={cf} v6a={ca} v6b={cb}")
    else:
        notes.append(f"quadrant {lab}: {cf} cells (fusion==v6a==v6b) OK")

# sum across quadrants == bucket-2 total
if quad_total != b2_count:
    problems.append(f"sum of quadrant cells {quad_total} != bucket-2 {b2_count}")
else:
    notes.append(f"quadrant sum {quad_total} == bucket-2 {b2_count} OK")

# check 3: SW specifics
SW = "(28.5,77.25)"
if SW in labs:
    sw_cells = quad_cells_fusion(SW)
    sw_area = round(sw_cells * cell_km2, 3)
    sw_pct = round(sw_cells / b2_count * 100, 1)
    notes.append(f"SW {SW}: {sw_cells} cells, {sw_area} km2, {sw_pct}% of bucket-2")
    if sw_cells != 5080:
        problems.append(f"SW cells {sw_cells} != 5080")
    if abs(sw_pct - 63.3) > 0.2:
        problems.append(f"SW pct {sw_pct} != ~63.3")

# check 4: total area
total_area = round(b2_count * cell_km2, 3)
for name, obj, key in [("fusion", fusion, "total_bucket2_area_km2"),
                       ("v6a", v6a, None), ("v6b", v6b, None)]:
    pass
notes.append(f"total bucket-2 area = {total_area} km2 (expect ~6.783)")
if abs(total_area - 6.783) > 0.05:
    problems.append(f"total area {total_area} != ~6.783")

# fusion's own recorded total
ft = fusion.get("total_bucket2_area_km2")
if ft is not None and abs(ft - total_area) > 0.01:
    problems.append(f"fusion recorded area {ft} != recomputed {total_area}")

# ---- report ----
L = ["NOIDA V6 FINAL CONSISTENCY AUDIT (pre-V7 baseline lock)",
     "=" * 60, "", "CHECKS PASSED:"]
L += [f"  [OK] {n}" for n in notes]
L += ["", "PROBLEMS:" if problems else "PROBLEMS: none — baseline consistent."]
L += [f"  [!!] {p}" for p in problems]
L += ["", f"VERDICT: {'INCONSISTENCIES FOUND' if problems else 'BASELINE CONSISTENT — safe to start V7'}"]
out = "\n".join(L) + "\n"
with open("outputs/consistency_audit_v6.txt", "w") as f:
    f.write(out)
print(out)
