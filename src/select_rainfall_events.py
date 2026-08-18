"""
V5 — RAINFALL EVENT SELECTION (frozen rule; run once, accept output)
===================================================================
Implements the FROZEN V5 event-selection rule on the archived 2015-2023
Jun-Sep hourly ERA5 series (outputs/rainfall_period_raw/). Selects events
objectively; parameters are NOT re-tuned after seeing results.

FROZEN RULE (physically justified; NOT derived from the data distribution):
    signal        : 4-cell equal-weight hourly mean (mm/h)
    wet hour      : precipitation >= 0.1 mm/h
    dry gap       : events separated by >= 6 consecutive DRY hours
    qualification : total >= 10 mm  AND  duration >= 3 h  AND  max rolling-6h >= 5 mm
    ranking       : max rolling-6h accumulation (descending)
    selection     : Top 10
    tie-break     : higher max 1-h intensity
    descriptors   : max 1-h, total (secondary; NOT used for ranking)
    NO post-hoc tuning.

Three hour states are distinguished (internal consistency):
    WET     : value present and >= 0.1 mm/h
    DRY     : value present and < 0.1 mm/h   (counts toward the 6-h dry gap)
    MISSING : value is None                  (does NOT count as dry; it breaks
              temporal continuity, ending the current event and any rolling run)
Here missing = 0 in the dataset, but the implementation is general and
self-consistent regardless.

Inputs : outputs/rainfall_period_raw/<cell>.json  (4 cells; times + precip)
Outputs: outputs/selected_rainfall_events.txt
         outputs/selected_rainfall_events.json
"""
import glob
import json
import numpy as np

RAW_DIR = "outputs/rainfall_period_raw"

# ---- FROZEN RULE CONSTANTS (do not tune) ----
WET_MM         = 0.1
DRY_GAP_H      = 6
MIN_TOTAL_MM   = 10.0
MIN_DURATION_H = 3
MIN_ROLL6_MM   = 5.0
ROLL_WINDOWS   = (1, 3, 6)
TOP_N          = 10

# hour-state codes
WET, DRY, MISSING = 1, 0, -1


def load_cells():
    files = sorted(glob.glob(f"{RAW_DIR}/*.json"))
    if len(files) != 4:
        raise ValueError(f"Expected 4 cell files in {RAW_DIR}, found {len(files)}")
    times_ref, cols = None, []
    for fp in files:
        with open(fp) as f:
            d = json.load(f)
        if times_ref is None:
            times_ref = d["times"]
        elif d["times"] != times_ref:
            raise ValueError(f"Timestamp mismatch in {fp}; cells not aligned.")
        cols.append(d["precipitation"])
    return times_ref, cols


def four_cell_mean(cols):
    """Equal-weight mean; None if ANY cell missing at that hour."""
    n = len(cols[0])
    return [None if any(c[i] is None for c in cols) else sum(c[i] for c in cols) / len(cols)
            for i in range(n)]


def hour_state(v):
    if v is None:
        return MISSING
    return WET if v >= WET_MM else DRY


def max_rolling(values, window):
    """Max sum over any contiguous `window`-hour run of PRESENT values.
    None breaks the run. If the longest present run is shorter than `window`,
    returns the max full-run sum among present runs (event shorter than window)."""
    best = 0.0
    run = []
    longest_full = 0.0
    for v in values:
        if v is None:
            if run:
                longest_full = max(longest_full, sum(run))
            run = []
            continue
        run.append(v)
        if len(run) >= window:
            best = max(best, sum(run[-window:]))
        longest_full = max(longest_full, sum(run))
    return best if best > 0.0 else longest_full


def main():
    times, cols = load_cells()
    mean = four_cell_mean(cols)
    n = len(mean)
    states = [hour_state(v) for v in mean]

    # ---- segment into events: start at WET, end when >= DRY_GAP_H consecutive
    #      DRY hours occur, OR a MISSING hour breaks continuity. ----
    events = []
    i = 0
    while i < n:
        if states[i] != WET:
            i += 1
            continue
        start = i
        last_wet = i
        dry_run = 0
        j = i + 1
        while j < n:
            st = states[j]
            if st == WET:
                last_wet = j
                dry_run = 0
            elif st == DRY:
                dry_run += 1
                if dry_run >= DRY_GAP_H:
                    break
            else:  # MISSING breaks continuity -> event ends
                break
            j += 1
        end = last_wet

        seg = mean[start:end + 1]
        seg_present = [v for v in seg if v is not None]
        total = sum(seg_present)
        duration = end - start + 1
        roll = {w: max_rolling(seg, w) for w in ROLL_WINDOWS}
        max1h = max(seg_present) if seg_present else 0.0

        events.append({
            "start": times[start], "end": times[end],
            "duration_h": duration,
            "total_mm": round(total, 2),
            "max_1h_mm": round(max1h, 2),
            "roll3_mm": round(roll[3], 2),
            "roll6_mm": round(roll[6], 2),
        })
        i = end + 1

    # ---- qualification ----
    qualified = [e for e in events
                 if e["total_mm"] >= MIN_TOTAL_MM
                 and e["duration_h"] >= MIN_DURATION_H
                 and e["roll6_mm"] >= MIN_ROLL6_MM]

    # ---- rank: max roll6 desc, tie-break max_1h desc ----
    qualified.sort(key=lambda e: (e["roll6_mm"], e["max_1h_mm"]), reverse=True)
    selected = qualified[:TOP_N]

    with open("outputs/selected_rainfall_events.json", "w") as f:
        json.dump({"rule": {
            "wet_mm": WET_MM, "dry_gap_h": DRY_GAP_H, "min_total_mm": MIN_TOTAL_MM,
            "min_duration_h": MIN_DURATION_H, "min_roll6_mm": MIN_ROLL6_MM,
            "ranking": "max_roll6_desc", "tie_break": "max_1h_desc", "top_n": TOP_N},
            "selected": selected}, f, indent=2)

    L = [
        "NOIDA V5 — SELECTED RAINFALL EVENTS (frozen rule; run once)",
        "=" * 66,
        "Signal: 4-cell equal-weight hourly mean, 2015-2023 Jun-Sep (ERA5).",
        "Rule (frozen): wet>=0.1mm/h; 6-h dry-gap separation (missing breaks",
        "  continuity, not counted as dry); qualify if total>=10mm AND",
        "  duration>=3h AND max-roll6>=5mm; rank by max-roll6 (desc), tie-break",
        "  max-1h; Top 10. max-1h & total are secondary descriptors. No tuning.",
        "",
        f"Total raw wet spells found     : {len(events):,}",
        f"Qualifying events              : {len(qualified):,}",
        f"Selected (Top {TOP_N})              : {len(selected)}",
        "",
        "SELECTED EVENTS (ranked by max rolling-6h)",
        f"  {'#':>2}  {'start':16s} {'dur_h':>5} {'total':>7} {'roll6':>7} {'roll3':>7} {'max1h':>6}",
    ]
    for r, e in enumerate(selected, 1):
        L.append(f"  {r:>2}  {e['start']:16s} {e['duration_h']:>5} "
                 f"{e['total_mm']:>7.1f} {e['roll6_mm']:>7.1f} "
                 f"{e['roll3_mm']:>7.1f} {e['max_1h_mm']:>6.1f}")
    L += [
        "",
        "NOTES",
        "  Events objectively selected by the frozen rule; parameters not tuned after",
        "  inspecting results. These are rainfall FORCING events, not observed",
        "  waterlogging. Per-cell metrics and fusion with V4 terrain/flow evidence",
        "  follow next. V2.1.1/V3/V4 remain frozen.",
    ]
    with open("outputs/selected_rainfall_events.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/selected_rainfall_events.txt")
    print("[ok] wrote outputs/selected_rainfall_events.json")
    print(f"[info] raw spells={len(events)}  qualified={len(qualified)}  selected={len(selected)}")


if __name__ == "__main__":
    main()
