"""
NOIDA FLOOD INTELLIGENCE — v2  (classical hydrology, clean spatial referencing)
WGS84 DEM -> UTM 44N -> NoData mask -> hydro-conditioning
-> flow dir -> flow accumulation -> slope -> TWI
-> analysis GeoTIFFs (UTM) -> viz RGBA -> reproject ONLY viz to WGS84 -> Folium
"""
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pysheds.grid import Grid
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import folium
import branca.colormap as bcm

DEM_WGS84 = "data/noida_dem.tif"
DEM_UTM   = "data/noida_dem_utm.tif"
UTM_CRS   = "EPSG:32644"
NODATA    = -9999.0
CMAP      = "YlGnBu"


def reproject_raster(src_path, dst_path, dst_crs, resampling,
                     src_nodata=None, dst_nodata=None):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        meta = src.meta.copy()
        meta.update(crs=dst_crs, transform=transform, width=width, height=height)
        if dst_nodata is not None:
            meta.update(nodata=dst_nodata)
        with rasterio.open(dst_path, "w", **meta) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform, src_crs=src.crs,
                    dst_transform=transform, dst_crs=dst_crs,
                    src_nodata=src_nodata, dst_nodata=dst_nodata,
                    resampling=resampling)
    return dst_path


def hillshade(arr, dx, dy, azimuth=315.0, altitude=45.0):
    az = np.radians(360.0 - azimuth + 90.0)
    alt = np.radians(altitude)
    dzdy, dzdx = np.gradient(arr, dy, dx)
    slope = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))
    aspect = np.arctan2(-dzdx, dzdy)
    shaded = (np.sin(alt) * np.cos(slope)
              + np.cos(alt) * np.sin(slope) * np.cos(az - aspect))
    return np.clip(shaded, 0, 1)


def save_single_band(ref_utm_path, array, out_path):
    with rasterio.open(ref_utm_path) as ref:
        profile = ref.profile
    profile.update(dtype="float32", count=1, nodata=np.nan)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(array.astype("float32"), 1)
    print(f"[ok] wrote {out_path}")


def main():
    reproject_raster(DEM_WGS84, DEM_UTM, UTM_CRS, Resampling.bilinear,
                     dst_nodata=NODATA)
    print(f"[ok] reprojected -> {DEM_UTM}")

    grid = Grid.from_raster(DEM_UTM)
    dem  = grid.read_raster(DEM_UTM)

    pit_filled = grid.fill_pits(dem)
    flooded    = grid.fill_depressions(pit_filled)
    inflated   = grid.resolve_flats(flooded)
    fdir       = grid.flowdir(inflated)
    acc        = grid.accumulation(fdir)

    dem_arr = np.asarray(dem, dtype="float64")
    nod = dem.nodata if dem.nodata is not None else NODATA
    valid = np.isfinite(dem_arr) & (dem_arr != nod)

    dx = abs(grid.affine.a)
    dy = abs(grid.affine.e)

    cond = np.asarray(inflated, dtype="float64")
    cond[~valid] = np.nan
    dzdy, dzdx = np.gradient(cond, dy, dx)
    slope = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))
    slope = np.where(slope < 1e-4, 1e-4, slope)

    acc_arr = np.asarray(acc, dtype="float64")
    a = (acc_arr + 1.0) * (dx * dy) / dx
    twi = np.log(a / np.tan(slope))
    twi[~valid] = np.nan

    depr = np.asarray(flooded, dtype="float64") - dem_arr
    depr[~valid] = np.nan
    depr = np.where(depr < 0, 0, depr)

    dem_for_hs = dem_arr.copy()
    dem_for_hs[~valid] = np.nan
    hs = hillshade(dem_for_hs, dx, dy)

    save_single_band(DEM_UTM, twi,  "outputs/twi_utm.tif")
    save_single_band(DEM_UTM, depr, "outputs/depression_depth_utm.tif")
    save_single_band(DEM_UTM, hs,   "outputs/hillshade_utm.tif")

    p2, p98 = np.nanpercentile(twi, 2), np.nanpercentile(twi, 98)
    with rasterio.open(DEM_UTM) as ref:
        b = ref.bounds
    extent = [b.left, b.right, b.bottom, b.top]

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(hs, cmap="gray", extent=extent, origin="upper")
    im = ax.imshow(np.ma.masked_invalid(twi), cmap=CMAP, alpha=0.65,
                   extent=extent, origin="upper", vmin=p2, vmax=p98)
    cb = plt.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label("Topographic Wetness Index  (higher = more waterlogging-prone)")
    ax.set_title("Noida — Waterlogging Risk (TWI, Copernicus GLO-30, UTM 44N)")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.savefig("outputs/waterlogging_static.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("[ok] wrote outputs/waterlogging_static.png")

    twi_norm = np.clip((twi - p2) / (p98 - p2 + 1e-9), 0, 1)
    rgb = cm.get_cmap(CMAP)(np.nan_to_num(twi_norm))[..., :3]
    shade = 0.5 + 0.5 * hs
    rgb = np.clip(rgb * shade[..., None], 0, 1)
    alpha = np.where(valid, 60 + 195 * twi_norm, 0)
    rgba = np.dstack([(rgb * 255), alpha]).astype("uint8")

    with rasterio.open(DEM_UTM) as ref:
        prof = ref.profile
    prof.update(count=4, dtype="uint8", nodata=None)
    with rasterio.open("outputs/viz_utm.tif", "w", **prof) as dst:
        for i in range(4):
            dst.write(rgba[..., i], i + 1)

    reproject_raster("outputs/viz_utm.tif", "outputs/viz_wgs84.tif",
                     "EPSG:4326", Resampling.nearest)

    with rasterio.open("outputs/viz_wgs84.tif") as v:
        img = np.transpose(v.read(), (1, 2, 0))
        vb = v.bounds
    plt.imsave("outputs/twi_overlay.png", img)
    bounds = [[vb.bottom, vb.left], [vb.top, vb.right]]
    center = [(vb.bottom + vb.top) / 2, (vb.left + vb.right) / 2]

    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")
    folium.raster_layers.ImageOverlay(
        image="outputs/twi_overlay.png", bounds=bounds,
        opacity=0.75, name="Waterlogging risk (TWI)").add_to(m)

    colors = [mcolors.rgb2hex(cm.get_cmap(CMAP)(i / 10.0)) for i in range(11)]
    legend = bcm.LinearColormap(
        colors=colors, vmin=float(p2), vmax=float(p98),
        caption="Topographic Wetness Index (higher = more waterlogging-prone)")
    legend.add_to(m)
    folium.LayerControl().add_to(m)
    m.save("outputs/waterlogging_map.html")
    print("[ok] wrote outputs/waterlogging_map.html")


if __name__ == "__main__":
    main()
