"""
V5 pre-step — RAINFALL PROVENANCE & DISTRIBUTION AUDIT (audit only)
==================================================================
Downloads ONE representative window from the Open-Meteo Historical Weather API
(dataset: ERA5, hourly precipitation) for the Noida study area and audits its
provenance + distribution BEFORE any V5 integration.

SOURCE (for the scientific record):
    Interface : Open-Meteo Historical Weather API (archive-api.open-meteo.com)
    Dataset   : ERA5 (reanalysis; NOT rain-gauge observation)
                ERA5-Land was tested separately and returned all-null
                precipitation on this endpoint/date window, so it was rejected.
    Variable  : precipitation
    Temporal  : hourly
    Native res: ~0.25 deg (~25 km)
    Unit      : mm (per hour)
    Role      : temporal rainfall FORCING plausibility, NOT observed waterlogging

This script does NOT touch the DEM, V2.1.1, V3, or V4 outputs, and performs NO
regridding of rainfall onto the 30 m DEM grid. It archives the raw response so
V5 is reproducible. The chosen window is a SOURCE-VALIDATION window, NOT a
declared V5 event.

Outputs (outputs/):
    rainfall_audit_raw.json      archived raw API response (+ request params)
    rainfall_audit_report.txt    provenance + distribution audit
"""
import json
import urllib.request
import urllib.parse
import numpy as np

# ---- Noida study-area representative point (centre-ish of DEM bbox) ----
REQ_LAT = 28.58
REQ_LON = 77.33

# ---- one representative window (source-validation only, NOT a V5 event) ----
START_DATE = "2023-07-08"
END_DATE   = "2023-07-10"

API   = "https://archive-api.open-meteo.com/v1/archive"
MODEL = "era5"


def fetch():
    params = {
        "latitude": REQ_LAT,
        "longitude": REQ_LON,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "precipitation",
        "models": MODEL,
        "timezone": "UTC",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read().decode())
    return params, url, data


def main():
    try:
        params, url, data = fetch()
    except Exception as e:
        print(f"[error] API request failed: {e}")
        print("        (This machine may lack network; run on your Mac.)")
        return

    # ---- archive raw response + request provenance ----
    archive = {"request_params": params, "request_url": url, "response": data}
    with open("outputs/rainfall_audit_raw.json", "w") as f:
        json.dump(archive, f, indent=2)
    print("[ok] archived outputs/rainfall_audit_raw.json")

    def g(k, default=None):
        return data.get(k, default)

    hourly = g("hourly", {}) or {}
    times = hourly.get("time", []) or []
    precip = hourly.get("precipitation", []) or []
    units = (g("hourly_units", {}) or {}).get("precipitation", "?")

    p = np.array([x for x in precip if x is not None], dtype="float64") \
        if precip else np.array([])
    n_total = len(precip)
    n_missing = sum(1 for x in precip if x is None)
    n_negative = int((p < 0).sum()) if p.size else 0

    # ---- timestep check ----
    def hours_between(a, b):
        from datetime import datetime
        fmt = "%Y-%m-%dT%H:%M"
        return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 3600.0
    steps_ok = "n/a"
    if len(times) >= 2:
        diffs = {round(hours_between(times[i], times[i+1]), 3) for i in range(len(times)-1)}
        steps_ok = (diffs == {1.0})

    # ---- consecutive wet hours (>0 mm) — audit-only proxy (None-stripped) ----
    wet = (p > 0).astype(int) if p.size else np.array([])
    max_wet_run = 0
    run = 0
    for w in wet:
        run = run + 1 if w else 0
        max_wet_run = max(max_wet_run, run)

    # ---- report ----
    L = [
        "NOIDA V5 PRE-STEP — RAINFALL PROVENANCE & DISTRIBUTION AUDIT",
        "=" * 64,
        "Source : Open-Meteo Historical Weather API -> ERA5",
        "         hourly precipitation (reanalysis, NOT gauge obs).",
        "         (ERA5-Land returned all-null precipitation for the tested",
        "          endpoint/date window and was therefore rejected for this",
        "          audit configuration; ERA5 used instead)",
        "Role   : temporal rainfall forcing plausibility, NOT observed",
        "         waterlogging. No DEM regridding. V2.1.1/V3/V4 untouched.",
        "         This window is source-validation, NOT a declared V5 event.",
        "",
        "PROVENANCE",
        f"  requested lat/lon    : {REQ_LAT}, {REQ_LON}",
        f"  returned lat/lon     : {g('latitude')}, {g('longitude')}  "
        "(actual ERA5 grid cell)",
        f"  returned elevation   : {g('elevation')}",
        f"  timezone             : {g('timezone')} / {g('timezone_abbreviation')}",
        f"  utc_offset_seconds   : {g('utc_offset_seconds')}",
        f"  requested dates      : {START_DATE} .. {END_DATE}",
        f"  first timestamp      : {times[0] if times else 'n/a'}",
        f"  last timestamp       : {times[-1] if times else 'n/a'}",
        f"  hourly timestep = 1h : {steps_ok}",
        f"  variable / unit      : precipitation / {units}",
        f"  model metadata       : models={params.get('models','?')} (as requested)",
        "",
        "DATA QUALITY",
        f"  total hourly steps   : {n_total:,}",
        f"  missing / None       : {n_missing:,}",
        f"  negative values      : {n_negative:,}",
        "",
        "DISTRIBUTION (hourly precip, mm)",
    ]
    if p.size:
        L += [
            f"  min                  : {np.min(p):.3f}",
            f"  P50                  : {np.percentile(p,50):.3f}",
            f"  P90                  : {np.percentile(p,90):.3f}",
            f"  P95                  : {np.percentile(p,95):.3f}",
            f"  max (1-hr peak)      : {np.max(p):.3f}",
            f"  total window rainfall: {np.sum(p):.3f} mm",
            f"  max consecutive wet h: {max_wet_run}  (audit proxy; V5 will preserve",
            "                         missing timestamps, not None-strip)",
        ]
    else:
        L.append("  (no precipitation values returned)")
    L += [
        "",
        "NOTES",
        "  ERA5 is reanalysis/model data, not direct rain-gauge observation.",
        "  Native resolution ~0.25 deg (~25 km): the whole Noida study area falls in",
        "  a very small number of grid cells, so rainfall provides temporal event",
        "  forcing, NOT fine spatial rainfall variation. IMD 0.25 deg daily gridded",
        "  rainfall is reserved for later independent cross-check (not used here).",
        "  The window total is NOT declared a 'heavy event'; event selection will",
        "  follow an objective rule in V5, not a convenient date.",
        "  Raw API response + request params archived in rainfall_audit_raw.json.",
    ]
    with open("outputs/rainfall_audit_report.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/rainfall_audit_report.txt")


if __name__ == "__main__":
    main()
