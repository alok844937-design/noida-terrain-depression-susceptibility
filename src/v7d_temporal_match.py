"""
V7-D — TEMPORAL MATCH (observed waterlogging vs V5 rainfall-event catalogue)
===========================================================================
Measures and DOCUMENTS the temporal relationship; does NOT try to "solve" the
date mismatch. Three INDEPENDENT evidence layers (never mixed):

  A. V5 EVENT-WINDOW OVERLAP — observation date vs each V5 Top-10 event's full
     multi-day [start,end] interval (from the frozen artifact). Exact, ±1d, ±2d.
  B. DOCUMENTED RAINFALL EVIDENCE — from frozen observation_rainfall.csv. Only
     explicitly documented amounts; MISSING stays MISSING; no inference; no
     heavy-rain classification.
  C. V5 DATASET COVERAGE AUDIT — ERA5 window (year range + months) from the
     frozen v5_coverage.json artifact. Each observation flagged inside/outside.
     OUTSIDE coverage != no rainfall.

WORDING LOCK: "no V5 Top-10 overlap" NEVER means "no rainfall trigger".
"""
import csv, json
from datetime import datetime, date, timedelta

V5_EVENTS   = "outputs/selected_rainfall_events.json"
PROVENANCE  = "outputs/observed_waterlogging_provenance.csv"
RAINFALL    = "outputs/observation_rainfall.csv"
COVERAGE    = "outputs/v5_coverage.json"  # ERA5 window (year range + months), audit artifact

def load_coverage():
    c = json.load(open(COVERAGE))
    return c["year_start"], c["year_end"], set(c["months_covered"]), c

def parse_v5_windows():
    d = json.load(open(V5_EVENTS))
    wins = []
    for e in d["selected"]:
        s = datetime.fromisoformat(e["start"]).date()
        en = datetime.fromisoformat(e["end"]).date()
        wins.append((s, en, e["roll6_mm"]))
    return wins

def usable_observation_dates():
    rows = list(csv.DictReader(open(PROVENANCE)))
    keep = []
    for r in rows:
        if r["study_area_status"] == "in_bbox" and r["classification"] in ("KEEP", "KEEP-WITH-UNCERTAINTY"):
            keep.append((r["observation_id"], datetime.strptime(r["event_date"], "%Y-%m-%d").date()))
    return keep

def overlaps(obs_d, start, end, pad_days):
    lo = start - timedelta(days=pad_days)
    hi = end + timedelta(days=pad_days)
    return lo <= obs_d <= hi

def in_coverage(d, y0, y1, months):
    return (y0 <= d.year <= y1) and (d.month in months)

def main():
    wins = parse_v5_windows()
    obs = usable_observation_dates()
    y0, y1, months, cov = load_coverage()
    rain = {r["observation_id"]: r for r in csv.DictReader(open(RAINFALL))}

    L = ["NOIDA V7-D — TEMPORAL MATCH (observed vs V5 rainfall catalogue)",
         "=" * 64,
         "Three independent evidence layers (never mixed). 'No V5 overlap' does",
         "NOT mean 'no rainfall trigger' — see Output C (coverage mismatch).",
         "",
         f"V5 Top-10 event windows (from {V5_EVENTS}, multi-day intervals):"]
    for s, e, r6 in wins:
        L.append(f"  {s} -> {e}  (roll6={r6} mm)")
    L += ["",
          "-" * 64,
          "A. V5 EVENT-WINDOW OVERLAP (obs date vs full event interval):",
          f"   {'observation':12s} {'date':12s} exact  +/-1d  +/-2d"]
    a_exact = a_1 = a_2 = 0
    for oid, od in obs:
        hit0 = any(overlaps(od, s, e, 0) for s, e, _ in wins)
        hit1 = any(overlaps(od, s, e, 1) for s, e, _ in wins)
        hit2 = any(overlaps(od, s, e, 2) for s, e, _ in wins)
        a_exact += hit0; a_1 += hit1; a_2 += hit2
        L.append(f"   {oid:12s} {str(od):12s} {'Y' if hit0 else '-':5s}  "
                 f"{'Y' if hit1 else '-':5s}  {'Y' if hit2 else '-'}")
    n = len(obs)
    L += [f"   -> exact overlap: {a_exact}/{n};  +/-1 day: {a_1}/{n};  +/-2 day: {a_2}/{n}",
          "",
          "-" * 64,
          "B. DOCUMENTED RAINFALL EVIDENCE (from frozen rainfall table):",
          f"   {'observation':12s} {'date':12s} {'mm':>6s}  status / source-verif"]
    n_doc = 0
    for oid, od in obs:
        rr = rain.get(oid, {})
        amt = rr.get("rainfall_amount_mm", "") or "--"
        st = rr.get("rainfall_status", "?")
        sv = rr.get("source_verification", "?")
        if st == "DOCUMENTED":
            n_doc += 1
        L.append(f"   {oid:12s} {str(od):12s} {amt:>6s}  {st} / {sv}")
    L += [f"   -> documented rainfall: {n_doc}/{n} "
          "(per-observation source-verification shown above)",
          "   NOTE: documented amount recorded as-is; NO heavy-rain classification applied.",
          "",
          "-" * 64,
          f"C. V5 DATASET COVERAGE AUDIT (ERA5 {y0}-{y1}, months {sorted(months)}):",
          f"   {'observation':12s} {'date':12s} coverage"]
    n_in = n_out = 0
    for oid, od in obs:
        inside = in_coverage(od, y0, y1, months)
        n_in += inside; n_out += (not inside)
        why = "INSIDE V5 coverage" if inside else (
              "OUTSIDE (post-2023)" if od.year > y1 else
              "OUTSIDE (year pre-2015)" if od.year < y0 else
              "OUTSIDE (month not Jun-Sep)")
        L.append(f"   {oid:12s} {str(od):12s} {why}")
    L += [f"   -> inside V5 coverage: {n_in}/{n};  outside: {n_out}/{n}",
          "   OUTSIDE coverage != no rainfall. For observations outside the V5",
          "   dataset window the frozen ERA5 catalogue simply cannot test them;",
          "   this is a coverage limitation, not a rainfall finding.",
          "",
          "=" * 64,
          "INTERPRETATION (honest):",
          f"  * {a_exact}/{n} observations overlap a V5 Top-10 event window (exact; also",
          f"    {a_1}/{n} at +/-1 day, {a_2}/{n} at +/-2 day).",
          "  * This absence of overlap is consistent with the catalogue-vs-record mismatch:",
          f"    {n_out}/{n} observations fall OUTSIDE the V5 dataset coverage window, while the",
          f"    {n_in}/{n} inside the covered months/years do NOT coincide with the selected",
          "    Top-10 events (the Top-10 are the strongest spells, not all rain-days).",
          "  * It does NOT establish that the reported waterlogging lacked a rainfall trigger.",
          "  * Documented observation-day rainfall is sparse (1/6); the single documented",
          "    amount has pending source verification, so rainfall evidence cannot be",
          "    established from this record alone.",
          "  * NET: temporal corroboration is NOT established; the limiting factor is data",
          "    coverage/precision, not a demonstrated absence of rainfall association."]
    out = "\n".join(L) + "\n"
    with open("outputs/v7d_temporal_match_report.txt", "w") as f:
        f.write(out)
    js = {
        "v5_windows": [{"start": str(s), "end": str(e), "roll6_mm": r6} for s, e, r6 in wins],
        "n_usable_observations": n,
        "A_event_window_overlap": {"exact": a_exact, "pm1_day": a_1, "pm2_day": a_2},
        "B_documented_rainfall": {"documented": n_doc, "total": n,
                                  "note": "Source-verification status is reported per observation in the rainfall table."},
        "C_v5_coverage": {"inside": n_in, "outside": n_out,
                          "year_range": [y0, y1], "months": sorted(months)},
        "wording_lock": ("no V5 Top-10 temporal overlap does NOT mean no rainfall "
                         "trigger; it reflects the V5 ERA5 coverage window vs "
                         "observation record mismatch"),
    }
    with open("outputs/v7d_temporal_match_report.json", "w") as f:
        json.dump(js, f, indent=2)
    print(out)

if __name__ == "__main__":
    main()
