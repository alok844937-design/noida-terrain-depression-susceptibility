"""
NOIDA FLOOD INTELLIGENCE — v1 (classical hydrology, NO ML / NO "AI")
Input : ek DEM GeoTIFF (Noida area).
Output: twi.tif, depression_depth.tif, waterlogging_map.html
"""
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pysheds.grid import Grid
import folium
import matplotlib.cm as cm
import matplotlib.pyplot as plt

DEM_PATH = "data/noida_dem.tif"
UTM_CRS  = "EPSG:32644"

def ensure_metric_crs(src_path, dst_path="data/noida_dem_utm.tif", dst_crs=UTM_CRS):
    with rasterio.open(src_path) as src:
        if src.crs and src.crs.to_string() == dst_crs:
            return src_path
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        meta = src.meta.copy()
        meta.update(crs=dst_crs, transform=transform, width=width, height=height)
        with rasterio.open(dst_path, "w", **meta) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform, src_crs=src.crs,
                    dst_transform=transform, dst_crs=dst_crs,
                    resampling=Resampling.bilinear)
    print(f"[ok] reprojected -> {dst_path}")
    return dst_path

def main():
    dem_path = ensure_metric_crs(DEM_PATH)
    grid = Grid.from_raster(dem_path)
    dem  = grid.read_raster(dem_path)

    pit_filled = grid.fill_pits(dem)
    flooded    = grid.fill_depressions(pit_filled)
    inflated   = grid.resolve_flats(flooded)
    fdir       = grid.flowdir(inflated)
    acc        = grid.accumulation(fdir)

    dx = abs(grid.affine.a); dy = abs(grid.affine.e)
    dem_arr = np.asarray(dem, dtype="float64")

    dzdy, dzdx = np.gradient(dem_arr, dy, dx)
    slope = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
    slope = np.where(slope < 1e-4, 1e-4, slope)

    acc_arr = np.asarray(acc, dtype="float64")
    a = (acc_arr + 1.0) * (dx * dy) / dx
    twi = np.log(a / np.tan(slope))

    depr = np.asarray(flooded, dtype="float64") - dem_arr
    depr = np.where(depr < 0, 0, depr)

    with rasterio.open(dem_path) as ref:
        profile = ref.profile
        profile.update(dtype="float32", count=1, nodata=np.nan)
    for arr, name in [(twi, "outputs/twi.tif"), (depr, "outputs/depression_depth.tif")]:
        with rasterio.open(name, "w", **profile) as dst:
            dst.write(arr.astype("float32"), 1)
        print(f"[ok] wrote {name}")

    with rasterio.open(DEM_PATH) as src84:
        b = src84.bounds
        south, west, north, east = b.bottom, b.left, b.top, b.right

    lo, hi = np.nanpercentile(twi, 2), np.nanpercentile(twi, 98)
    tn = np.clip((twi - lo) / (hi - lo), 0, 1)
    rgba = cm.get_cmap("Blues")(tn)
    plt.imsave("outputs/twi_overlay.png", rgba)

    m = folium.Map(location=[(south + north) / 2, (west + east) / 2],
                   zoom_start=12, tiles="CartoDB positron")
    folium.raster_layers.ImageOverlay(
        image="outputs/twi_overlay.png",
        bounds=[[south, west], [north, east]],
        opacity=0.6, name="Waterlogging risk (TWI)").add_to(m)
    folium.LayerControl().add_to(m)
    m.save("outputs/waterlogging_map.html")
    print("[ok] wrote outputs/waterlogging_map.html")

if __name__ == "__main__":
    main()
