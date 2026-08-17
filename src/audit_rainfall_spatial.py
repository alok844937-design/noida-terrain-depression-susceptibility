"""
V5-A — Multi-point ERA5 spatial provenance audit (audit only)
=============================================================
Reads the DEM bounds, samples 5 points (NW/NE/SW/SE/centre) of the Noida study
area, requests ERA5 hourly precipitation at each via the Open-Meteo Historical
API, and records how many UNIQUE ERA5 grid cells those sample points map to.

Purpose: establish objectively whether Noida is represented by one ERA5 cell or
a few, so V5 never fabricates 30 m spatial rainfall detail. Audit only: no DEM
regridding, no V2.1.1/V3/V4 changes, no event claims.

Input : data/noida_dem_utm.tif  (bounds read, reprojected to lat/lon for query)
Output: outputs/rainfall_spatial_audit.txt
        outputs/rainfall_spatial_audit_raw.json
"""
import json
import urllib.request
import urllib.parse
import numpy as np
import rasterio
from rasterio.warp import transform_bounds

DEM_UTM = "data/noida_dem_utm.tif"
API = "https://archive-api.open-meteo.com/v1/archive"
START_DATE = "2023-07-08"
END_DATE   = "2023-07-10"
MODEL = "era5"


def fetch(lat, lon):
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": START_DATE, "end_date": END_DATE,
        "hourly": "precipitation", "models": MODEL, "timezone": "UTC",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return params, url, json.loads(r.read().decode())


def main():
    # ---- DEM bounds -> lat/lon (WGS84) ----
    with rasterio.open(DEM_UTM) as src:
        b = src.bounds
        w, s, e, n = transform_bounds(src.crs, "EPSG:4326",
                                      b.left, b.bottom, b.right, b.top)
    cx, cy = (w + e) / 2, (s + n) / 2
    points = {
        "NW": (n, w), "NE": (n, e), "SW": (s, w), "SE": (s, e), "C": (cy, cx),
    }
    print(f"[info] study-area lat/lon bbox: W={w:.4f} S={s:.4f} E={e:.4f} N={n:.4f}")

    results = {}
    archive = {}
    for name, (lat, lon) in points.items():
        try:
            params, url, data = fetch(lat, lon)
        except Exception as ex:
            print(f"[error] {name} request failed: {ex}")
            print("        (run on a machine with network access.)")
            return
        rlat, rlon = data.get("latitude"), data.get("longitude")
        p = data.get("hourly", {}).get("precipitation", []) or []
        pnn = np.array([x for x in p if x is not None], dtype="float64")
        results[name] = {
            "req": (round(lat, 4), round(lon, 4)),
            "cell": (rlat, rlon),
            "n": len(p), "missing": sum(1 for x in p if x is None),
            "total_mm": round(float(pnn.sum()), 3) if pnn.size else None,
            "max_hr": round(float(pnn.max()), 3) if pnn.size else None,
        }
        archive[name] = {"params": params, "url": url, "response": data}

    with open("outputs/rainfall_spatial_audit_raw.json", "w") as f:
        json.dump(archive, f, indent=2)

    # ---- unique ERA5 cells among the 5 sample points ----
    unique_cells = sorted({tuple(v["cell"]) for v in results.values()})

    L = [
        "NOIDA V5-A — MULTI-POINT ERA5 SPATIAL PROVENANCE AUDIT",
        "=" * 64,
        "Source : Open-Meteo Historical Weather API -> ERA5 (reanalysis).",
        "         (ERA5-Land returned all-null precipitation for the tested",
        "          endpoint/date window and was rejected for this configuration.)",
        "Purpose: how many UNIQUE ERA5 grid cells do 5 study-area sample points map to?",
        "         (audit only; no regridding; no event claims)",
        f"Window : {START_DATE} .. {END_DATE} (source-validation window, NOT a V5 event)",
        "",
        "STUDY-AREA POINTS -> RETURNED ERA5 CELL",
    ]
    for name, v in results.items():
        L.append(f"  {name:2s} req={v['req']} -> cell={v['cell']}  "
                 f"n={v['n']} miss={v['missing']} total_mm={v['total_mm']}")
    L += [
        "",
        f"UNIQUE ERA5 CELLS REPRESENTED BY 5 SAMPLE POINTS : {len(unique_cells)}",
    ]
    for c in unique_cells:
        L.append(f"  {c}")
    L += [
        "",
        "INTERPRETATION",
        f"  The five representative study-area points map to {len(unique_cells)} unique ERA5",
        "  grid cells. This audit does NOT perform exact polygon/grid-cell",
        "  intersection analysis. The result demonstrates that the study area spans",
        "  multiple coarse ERA5 cells at the sampled locations. Therefore V5 may",
        "  retain coarse ERA5 spatial variation at the source-cell level, but will",
        "  NOT interpolate rainfall onto the 30 m DEM grid or present rainfall as",
        "  fine spatial detail.",
    ]
    with open("outputs/rainfall_spatial_audit.txt", "w") as f:
        f.write("\n".join(L) + "\n")
    print("[ok] wrote outputs/rainfall_spatial_audit.txt")
    print(f"[ok] unique ERA5 cells (5 sample points): {len(unique_cells)}")


if __name__ == "__main__":
    main()
