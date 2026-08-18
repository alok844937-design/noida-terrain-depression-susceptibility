"""
V5-C — Multi-year monsoon PERIOD AUDIT (audit only; no event selection)
======================================================================
Downloads hourly ERA5 precipitation (Open-Meteo Historical API) for June-September
2015-2023 at the FOUR ERA5 cells represented by the five spatial-audit sample
points, and audits dataset usability BEFORE any event-selection rule is written.

Checks: timestamp alignment across cells, missing values / gaps, duplicate
timestamps, per-cell availability, units/model/grid-cell provenance, and a basic
rainfall distribution. Selects NO event, applies NO threshold, touches NO V4/V5
outputs.

The 4-cell mean here is "the mean of the four ERA5 cells represented by the five
spatial-audit points" — NOT an exact area-weighted Noida rainfall.

Output:
    outputs/rainfall_period_audit.txt
    outputs/rainfall_period_raw/<cell>.json   (archived per-cell responses)
"""
import os
import json
import time
import urllib.request
import urllib.parse
import numpy as np
from datetime import datetime

API   = "https://archive-api.open-meteo.com/v1/archive"
MODEL = "era5"

# the four ERA5 cells represented by the five spatial-audit points
CELLS = [(28.5, 77.25), (28.5, 77.5), (28.75, 77.25), (28.75, 77.5)]

YEARS  = list(range(2015, 2024))   # 2015..2023
MONTHS = "06-01", "09-30"          # June 1 .. September 30 each year

ARCHIVE_DIR = "outputs/rainfall_period_raw"


def fetch(lat, lon, start, end):
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "hourly": "precipitation", "models": MODEL, "timezone": "UTC",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return params, url, json.loads(r.read().decode())


def cell_key(lat, lon):
    return f"{lat}_{lon}".replace(".", "p")


def main():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # ---- download each cell, each monsoon year, concatenate ----
    per_cell_times = {}     # cell -> list of ISO timestamps
    per_cell_precip = {}    # cell -> list of precip (None preserved)
    provenance = {}         # cell -> returned lat/lon/elev/units

    for (lat, lon) in CELLS:
        times, precip = [], []
        for y in YEARS:
            start, end = f"{y}-{MONTHS[0]}", f"{y}-{MONTHS[1]}"
            try:
                params, url, data = fetch(lat, lon, start, end)
            except Exception as ex:
                print(f"[error] cell {lat},{lon} {y} failed: {ex}")
                print("        (run on a machine with network access.)")
                return
            h = data.get("hourly", {}) or {}
            times += h.get("time", []) or []
            precip += h.get("precipitation", []) or []
            if (lat, lon) not in provenance:
                provenance[(lat, lon)] = {
                    "ret_lat": data.get("latitude"),
                    "ret_lon": data.get("longitude"),
                    "elev": data.get("elevation"),
                    "unit": (data.get("hourly_units", {}) or {}).get("precipitation", "?"),
                    "model": params.get("models"),
                }
            time.sleep(0.3)   # be polite to the API
        per_cell_times[(lat, lon)] = times
        per_cell_precip[(lat, lon)] = precip
        with open(f"{ARCHIVE_DIR}/{cell_key(lat,lon)}.json", "w") as f:
            json.dump({"times": times, "precipitation": precip,
                       "provenance": provenance[(lat, lon)]}, f)
        print(f"[ok] archived cell {lat},{lon}: {len(times):,} hourly steps")

    # ---- alignment check: all cells must share identical timestamp vectors ----
    ref = per_cell_times[CELLS[0]]
    aligned = all(per_cell_times[c] == ref for c in CELLS)

    # ---- duplicates ----
    dup_counts = {c: len(per_cell_times[c]) - len(set(per_cell_times[c])) for c in CELLS}

    # ---- expected vs actual hours (gap check) ----
    def expected_hours():
        tot = 0
        for y in YEARS:
            a = datetime.strptime(f"{y}-{MONTHS[0]}T00:00", "%Y-%m-%dT%H:%M")
            b = datetime.strptime(f"{y}-{MONTHS[1]}T23:00", "%Y-%m-%dT%H:%M")
            tot += int((b - a).total_seconds() // 3600) + 1
        return tot
    exp_hours = expected_hours()

    # ---- per-cell missing + distribution ----
    stats = {}
    for c in CELLS:
        p = per_cell_precip[c]
        arr = np.array([x for x in p if x is not None], dtype="float64")
        stats[c] = {
            "steps": len(p),
            "missing": sum(1 for x in p if x is None),
            "negative": int((arr < 0).sum()) if arr.size else 0,
            "P50": float(np.percentile(arr, 50)) if arr.size else float("nan"),
            "P95": float(np.percentile(arr, 95)) if arr.size else float("nan"),
            "P99": float(np.percentile(arr, 99)) if arr.size else float("nan"),
            "max": float(arr.max()) if arr.size else float("nan"),
        }

    # ---- 4-cell mean (only where ALL cells present at a timestep) ----
    mean_series = []
    if aligned:
        n = len(ref)
        mats = [per_cell_precip[c] for c in CELLS]
        both_missing = 0
        for i in range(n):
            vals = [m[i] for m in mats]
            if any(v is None for v in vals):
                mean_series.append(None)
                both_missing += 1
            else:
                mean_series.append(sum(vals) / len(vals))
        marr = np.array([x for x in mean_series if x is not None], dtype="float64")
    else:
        marr = np.array([])
        both_missing = None

    # ---- report ----
    L = [
        "NOIDA V5-C — MULTI-YEAR MONSOON PERIOD AUDIT (audit only)",
        "=" * 64,
        "Source : Open-Meteo Historical Weather API -> ERA5 (reanalysis).",
        f"Period : {YEARS[0]}-{YEARS[-1]}, June-September, hourly.",
        "Cells  : the four ERA5 cells represented by the five spatial-audit points.",
        "         The 4-cell mean is an EQUAL-WEIGHT mean of four represented ERA5",
        "         source cells, NOT an area-weighted rainfall estimate for the",
        "         Noida polygon.",
        "Purpose: dataset usability only. NO event selected, NO threshold applied,",
        "         V4/V5 outputs untouched.",
        "",
        "GRID-CELL PROVENANCE",
    ]
    for c in CELLS:
        pr = provenance[c]
        L.append(f"  requested {c} -> returned ({pr['ret_lat']}, {pr['ret_lon']}) "
                 f"elev={pr['elev']} unit={pr['unit']} model={pr['model']}")
    L += [
        "",
        "TIMESTAMP INTEGRITY",
        f"  all 4 cells timestamp-aligned : {aligned}",
        f"  expected hours (Jun-Sep x9yr) : {exp_hours:,}",
        f"  actual hours per cell         : {len(ref):,}",
        f"  actual == expected            : {len(ref) == exp_hours}",
        f"  duplicate timestamps per cell : {dup_counts}",
        "",
        "PER-CELL DATA QUALITY + DISTRIBUTION (mm)",
    ]
    for c in CELLS:
        s = stats[c]
        L.append(f"  {c}: steps={s['steps']:,} miss={s['missing']} neg={s['negative']} "
                 f"P50={s['P50']:.2f} P95={s['P95']:.2f} P99={s['P99']:.2f} max={s['max']:.2f}")
    L += [
        "",
        "4-CELL EQUAL-WEIGHT MEAN SERIES (candidate event-detection basis;",
        " when all 4 cells are present)",
    ]
    if marr.size:
        L += [
            f"  usable mean steps (all cells present) : {marr.size:,}",
            f"  steps with >=1 cell missing           : {both_missing:,}",
            f"  mean P50 / P95 / P99 / max (mm)        : "
            f"{np.percentile(marr,50):.2f} / {np.percentile(marr,95):.2f} / "
            f"{np.percentile(marr,99):.2f} / {marr.max():.2f}",
        ]
    else:
        L.append("  (cells not aligned or no data — mean not computed)")
    L += [
        "",
        "VERDICT NOTES",
        "  This audit only establishes whether the multi-year monsoon dataset is",
        "  usable (aligned, low-missing, no duplicates, sane distribution). The",
        "  event-selection RULE is written separately and independently AFTER this,",
        "  and will NOT be tuned by looking at these numbers. Per-cell series are",
        "  archived under outputs/rainfall_period_raw/ for reproducibility.",
    ]
    with open("outputs/rainfall_period_audit.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/rainfall_period_audit.txt")


if __name__ == "__main__":
    main()
