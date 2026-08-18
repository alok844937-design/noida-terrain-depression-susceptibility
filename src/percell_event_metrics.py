"""
V5 — PER-CELL METRICS for the frozen Top-10 rainfall events (characterize only)
==============================================================================
The 10 events were selected by the frozen rule on the 4-cell MEAN (WHEN). This
step characterizes each frozen event across the FOUR ERA5 cells (WHERE/HOW MUCH).
It does NOT re-select or re-rank events. Event windows are taken verbatim from
outputs/selected_rainfall_events.json.

Per event x cell:
    total mm, max 1h, max 3h, max 6h, duration (event window is fixed by the
    mean-based selection; duration is the same across cells).
Per event (spatial summary across 4 cells):
    wettest cell, driest cell, spatial range (max-min total), each cell's total
    relative to the 4-cell mean total.

Inputs : outputs/selected_rainfall_events.json
         outputs/rainfall_period_raw/<cell>.json  (4 cells; aligned timestamps)
Outputs: outputs/percell_event_metrics.txt
         outputs/percell_event_metrics.json
"""
import glob
import json

RAW_DIR = "outputs/rainfall_period_raw"
ROLL_WINDOWS = (1, 3, 6)


def load_cells():
    files = sorted(glob.glob(f"{RAW_DIR}/*.json"))
    if len(files) != 4:
        raise ValueError(f"Expected 4 cell files, found {len(files)}")
    times_ref, series = None, {}
    for fp in files:
        with open(fp) as f:
            d = json.load(f)
        if times_ref is None:
            times_ref = d["times"]
        elif d["times"] != times_ref:
            raise ValueError(f"Timestamp mismatch in {fp}")
        # label each cell by its returned grid coordinate
        prov = d.get("provenance", {})
        label = f"({prov.get('ret_lat')},{prov.get('ret_lon')})"
        series[label] = d["precipitation"]
    # build index lookup for timestamps
    tindex = {t: i for i, t in enumerate(times_ref)}
    return times_ref, tindex, series


def max_rolling(vals, window):
    """Max contiguous-window sum; None breaks the run; short runs use full sum."""
    best, run, longest = 0.0, [], 0.0
    for v in vals:
        if v is None:
            if run:
                longest = max(longest, sum(run))
            run = []
            continue
        run.append(v)
        if len(run) >= window:
            best = max(best, sum(run[-window:]))
        longest = max(longest, sum(run))
    return round(best if best > 0.0 else longest, 2)


def main():
    with open("outputs/selected_rainfall_events.json") as f:
        sel = json.load(f)
    events = sel["selected"]

    times, tindex, series = load_cells()
    cell_labels = list(series.keys())

    out_events = []
    for rank, e in enumerate(events, 1):
        i0, i1 = tindex[e["start"]], tindex[e["end"]]
        percell = {}
        for lab in cell_labels:
            seg = series[lab][i0:i1 + 1]
            present = [v for v in seg if v is not None]
            percell[lab] = {
                "total_mm": round(sum(present), 2),
                "max_1h_mm": round(max(present), 2) if present else 0.0,
                "max_3h_mm": max_rolling(seg, 3),
                "max_6h_mm": max_rolling(seg, 6),
            }
        totals = {lab: percell[lab]["total_mm"] for lab in cell_labels}
        wettest = max(totals, key=totals.get)
        driest  = min(totals, key=totals.get)
        mean_total = round(sum(totals.values()) / len(totals), 2)
        spatial_range = round(totals[wettest] - totals[driest], 2)
        # each cell's total relative to the 4-cell mean total
        rel = {lab: (round(totals[lab] / mean_total, 2) if mean_total else None)
               for lab in cell_labels}

        out_events.append({
            "rank": rank, "start": e["start"], "end": e["end"],
            "duration_h": e["duration_h"],
            "mean_total_mm": mean_total,
            "wettest_cell": wettest, "driest_cell": driest,
            "spatial_range_mm": spatial_range,
            "percell": percell, "relative_to_mean": rel,
        })

    with open("outputs/percell_event_metrics.json", "w") as f:
        json.dump({"cells": cell_labels, "events": out_events}, f, indent=2)

    L = [
        "NOIDA V5 — PER-CELL METRICS FOR FROZEN TOP-10 EVENTS (characterize only)",
        "=" * 72,
        "Events fixed by the frozen mean-based selection; NOT re-selected/re-ranked.",
        "Per-cell metrics show WHERE/HOW MUCH within each already-frozen event.",
        f"Cells (returned ERA5 grid coords): {cell_labels}",
        "",
    ]
    for e in out_events:
        L.append(f"[{e['rank']:>2}] {e['start']}  dur={e['duration_h']}h  "
                 f"mean_total={e['mean_total_mm']}mm  range={e['spatial_range_mm']}mm")
        L.append(f"     wettest={e['wettest_cell']}  driest={e['driest_cell']}")
        for lab in cell_labels:
            pc = e["percell"][lab]
            L.append(f"       {lab:20s} total={pc['total_mm']:>6.1f} "
                     f"max1h={pc['max_1h_mm']:>5.1f} max3h={pc['max_3h_mm']:>6.1f} "
                     f"max6h={pc['max_6h_mm']:>6.1f}  rel={e['relative_to_mean'][lab]}")
        L.append("")
    L += [
        "NOTES",
        "  This characterizes spatial rainfall distribution WITHIN frozen events at",
        "  the coarse (~25 km) ERA5 cell level. It is NOT 30 m rainfall detail and is",
        "  NOT observed waterlogging. Event windows come verbatim from the frozen",
        "  selection. Fusion with V4 terrain/flow evidence is a separate later step.",
    ]
    with open("outputs/percell_event_metrics.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/percell_event_metrics.txt")
    print("[ok] wrote outputs/percell_event_metrics.json")


if __name__ == "__main__":
    main()
