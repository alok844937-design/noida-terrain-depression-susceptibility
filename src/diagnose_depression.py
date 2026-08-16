import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INPUT = "outputs/depression_depth_utm.tif"
OUT = "outputs/depression_depth_histogram.png"

with rasterio.open(INPUT) as src:
    arr = src.read(1, masked=True).compressed()
    pixel_width, pixel_height = src.res

pixel_area_m2 = abs(pixel_width * pixel_height)

print("\n=== DEPRESSION DEPTH DIAGNOSTIC ===")
print(f"Valid cells: {len(arr):,}")
print(f"Pixel size: {pixel_width:.2f} x {pixel_height:.2f} m")
print(f"Pixel area: {pixel_area_m2:.2f} m²")

print("\n--- Percentiles ---")
for p in [50, 75, 90, 95, 99, 99.9]:
    print(f"P{p}: {np.percentile(arr, p):.4f} m")

print("\n--- Depth bands ---")
bands = [
    ("0–0.1 m", 0, 0.1),
    ("0.1–0.2 m", 0.1, 0.2),
    ("0.2–0.5 m", 0.2, 0.5),
    ("0.5–1 m", 0.5, 1),
    ("1–2 m", 1, 2),
    ("2–3 m", 2, 3),
    ("3–5 m", 3, 5),
    ("5–10 m", 5, 10),
    (">10 m", 10, np.inf),
]

for name, lo, hi in bands:
    mask = (arr >= lo) & (arr < hi)
    count = int(mask.sum())
    area_km2 = count * pixel_area_m2 / 1e6
    pct = count / len(arr) * 100
    print(f"{name:12s}: {count:8,} cells | {area_km2:8.3f} km² | {pct:7.3f}%")

# Candidate band — diagnostic only, NOT confirmed waterlogging
candidate = (arr >= 0.2) & (arr <= 2.0)
print("\n--- Candidate 0.2–2 m band ---")
print(f"Cells : {candidate.sum():,}")
print(f"Area  : {candidate.sum() * pixel_area_m2 / 1e6:.3f} km²")
print(f"Share : {candidate.mean() * 100:.3f}%")

# Histogram
plt.figure(figsize=(10, 6))

# Focused histogram for 0–5 m
focused = arr[(arr >= 0) & (arr <= 5)]

plt.hist(focused, bins=100)
plt.axvline(0.2, linestyle="--", label="0.2 m")
plt.axvline(2.0, linestyle="--", label="2.0 m")
plt.xlabel("Depression depth (m)")
plt.ylabel("Number of cells")
plt.title("Noida — Depression Depth Distribution")
plt.legend()
plt.tight_layout()
plt.savefig(OUT, dpi=160)
plt.close()

print(f"\n[ok] wrote {OUT}")
