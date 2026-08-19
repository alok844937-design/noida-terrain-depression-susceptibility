"""
V7-A — OBSERVED WATERLOGGING PROVENANCE AUDIT (summary of the provenance table)
==============================================================================
Reads outputs/observed_waterlogging_provenance.csv and reports the composition:
verification status, source tiers, spatial precision, study-area membership,
and classification. Makes NO validation claim; this is a provenance summary.

Terminology: these are "observed waterlogging reports", NOT ground truth.
Nothing here is matched to susceptibility yet.
"""
import csv
from collections import Counter

CSV = "outputs/observed_waterlogging_provenance.csv"

def main():
    rows = list(csv.DictReader(open(CSV)))
    n = len(rows)
    def dist(field):
        return dict(Counter(r[field] for r in rows))

    L = [
        "NOIDA V7-A — OBSERVED WATERLOGGING PROVENANCE AUDIT",
        "=" * 60,
        "These are OBSERVED WATERLOGGING REPORTS (sector/landmark precision),",
        "NOT ground truth and NOT yet matched to susceptibility. Every record keeps",
        "verbatim location text + source + a verification_status flag.",
        "",
        f"Total records                : {n}",
        f"verification_status          : {dist('verification_status')}",
        f"study_area_status            : {dist('study_area_status')}",
        f"classification               : {dist('classification')}",
        f"source_tier                  : {dist('source_tier')}",
        f"spatial_precision_class      : {dist('spatial_precision_class')}",
        f"officially_reported          : {dist('officially_reported')}",
        "",
        "NOTE: source_tier != verification_status. Tier = the source's CLAIMED",
        "  origin (official/news); verification = whether WE independently re-checked",
        "  it. e.g. Tier-A + USER-REPORTED = claims an official origin, not yet",
        "  re-verified by us. Both are recorded honestly and separately.",
        "",
        "USABLE FOR VALIDATION (KEEP / KEEP-WITH-UNCERTAINTY, in_bbox):",
    ]
    usable = [r for r in rows
              if r["classification"] in ("KEEP", "KEEP-WITH-UNCERTAINTY")
              and r["study_area_status"] == "in_bbox"]
    for r in usable:
        L.append(f"  [{r['observation_id']:11s}] {r['event_date']}  "
                 f"{r['spatial_precision_class']:12s} tier-{r['source_tier']} "
                 f"{r['verification_status']}")
    L += [
        "",
        f"  -> {len(usable)} records pass the usability filter (KEEP/KEEP-WITH-"
        f"UNCERTAINTY, in_bbox); only "
        f"{sum(1 for r in usable if r['verification_status']=='VERIFIED')} are independently VERIFIED; "
        f"{sum(1 for r in usable if r['verification_status']=='USER-REPORTED')} are user-reported (source pending).",
        "",
        "HONEST DATA-AVAILABILITY VERDICT",
        "  Observed waterlogging evidence exists at sector/landmark precision from",
        "  official (Tier A) and news (Tier B) sources. BUT: (a) no public downloadable",
        "  point-level complaint database was found; (b) several candidate reports could",
        "  not be re-verified to an exact source URL in this pass; (c) sector-level",
        "  precision is COARSER than the 30 m susceptibility grid. Therefore V7 supports",
        "  QUALITATIVE corroboration only, NOT quantitative cell-level validation.",
    ]
    out = "\n".join(L) + "\n"
    with open("outputs/observed_provenance_audit_v7a.txt", "w") as f:
        f.write(out)
    print(out)

if __name__ == "__main__":
    main()
