"""Remote HiRISE image access and resampling onto a common analysis grid.

Primary source: USGS Astrogeology analysis-ready Cloud-Optimized GeoTIFFs of
the PDS HiRISE RED RDRs (doi:10.5066/P944DLP8), read with HTTP range requests
through GDAL ``/vsicurl/``; only the blocks needed are transferred and internal
overviews are used for coarse reads. Fallback: the original PDS JPEG2000 RDR
(much slower random access, ~50 s per 512² window in our tests).

Both images of a pair are resampled into one :class:`Grid` — a north-up local
Lambert azimuthal equal-area projection on the Mars sphere centred on the
overlap — so pixels are square, equal-area and directly comparable.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS as RioCRS
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from .config import settings
from .geometry import local_laea
from .log import get_logger

log = get_logger("imagery")

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.JP2,.jp2",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    GDAL_HTTP_MAX_RETRY="4",
    GDAL_HTTP_RETRY_DELAY="2",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE=str(64 * 1024 * 1024),
    GDAL_CACHEMAX=settings.gdal_cache_mb * 1024 * 1024,
)


def cog_url(product_id: str) -> str:
    return f"{settings.cog_base}/{product_id}/{product_id}.tif"


def cog_thumbnail_url(product_id: str) -> str:
    return f"{settings.cog_base}/{product_id}/{product_id}.jpg"


def pds_jp2_url(pds_path: str) -> str:
    return f"{settings.pds_base}/{pds_path}"


def pds_label_url(pds_path: str) -> str:
    return f"{settings.pds_base}/{pds_path.rsplit('.', 1)[0]}.LBL"


def uahirise_url(observation_id: str) -> str:
    return f"{settings.uahirise_base}/{observation_id}"


class RateLimiter:
    """Simple token bucket shared by all remote reads (politeness to archives)."""

    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = rate
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.rate, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                time.sleep((1 - self.tokens) / self.rate)


_limiter = RateLimiter(settings.requests_per_second)


class ReadStats:
    """Process-wide counters surfaced in the processing console."""

    lock = threading.Lock()
    reads = 0
    pixels = 0
    seconds = 0.0
    cache_hits = 0
    failures = 0

    @classmethod
    def snapshot(cls) -> dict:
        with cls.lock:
            return dict(reads=cls.reads, pixels=cls.pixels, seconds=round(cls.seconds, 2),
                        cache_hits=cls.cache_hits, failures=cls.failures)


@dataclass(frozen=True)
class Grid:
    """A north-up raster grid in a local LAEA projection."""

    crs_wkt: str
    transform: tuple[float, ...]
    width: int
    height: int

    @property
    def affine(self) -> Affine:
        return Affine(*self.transform[:6])

    @property
    def res(self) -> float:
        return abs(self.transform[0])

    @property
    def crs(self) -> RioCRS:
        return RioCRS.from_wkt(self.crs_wkt)

    def key(self) -> str:
        return hashlib.sha1(json.dumps([self.crs_wkt, self.transform, self.width, self.height]).encode()).hexdigest()[:16]

    def subgrid(self, x0: int, y0: int, w: int, h: int) -> "Grid":
        a = self.affine * Affine.translation(x0, y0)
        return Grid(self.crs_wkt, tuple(a)[:6], w, h)

    def pixel_to_lonlat(self, col: float, row: float) -> tuple[float, float]:
        from .geometry import from_local
        from pyproj import CRS

        x, y = self.affine * (col, row)
        lon, lat = from_local(CRS.from_wkt(self.crs_wkt)).transform(x, y)
        return lon % 360.0, lat

    def lonlat_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        from .geometry import to_local
        from pyproj import CRS

        x, y = to_local(CRS.from_wkt(self.crs_wkt)).transform(lon, lat)
        col, row = ~self.affine * (x, y)
        return col, row

    def to_dict(self) -> dict:
        return {"crs_wkt": self.crs_wkt, "transform": list(self.transform), "width": self.width, "height": self.height}

    @staticmethod
    def from_dict(d: dict) -> "Grid":
        return Grid(d["crs_wkt"], tuple(d["transform"]), d["width"], d["height"])


def make_grid(center_lat: float, center_lon: float, half_w_m: float, half_h_m: float, res_m: float) -> Grid:
    crs = local_laea(center_lat, center_lon)
    w = int(math.ceil(2 * half_w_m / res_m))
    h = int(math.ceil(2 * half_h_m / res_m))
    t = Affine(res_m, 0, -w * res_m / 2, 0, -res_m, h * res_m / 2)
    return Grid(crs.to_wkt(), tuple(t)[:6], w, h)


def grid_for_polygon(poly_lonlat, res_m: float, pad_m: float = 0.0, max_area_km2: float | None = None) -> Grid:
    """Grid covering a lon/lat polygon (e.g. the overlap of two footprints)."""
    from .geometry import project_polygon

    c = poly_lonlat.centroid
    crs = local_laea(c.y, c.x)
    p = project_polygon(poly_lonlat, crs)
    minx, miny, maxx, maxy = p.bounds
    minx, miny, maxx, maxy = minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m
    if max_area_km2 and (maxx - minx) * (maxy - miny) / 1e6 > max_area_km2:
        # keep the centre portion of the overlap within the area budget
        scale = math.sqrt(max_area_km2 * 1e6 / ((maxx - minx) * (maxy - miny)))
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        hw, hh = (maxx - minx) * scale / 2, (maxy - miny) * scale / 2
        minx, maxx, miny, maxy = cx - hw, cx + hw, cy - hh, cy + hh
    w = int(math.ceil((maxx - minx) / res_m))
    h = int(math.ceil((maxy - miny) / res_m))
    t = Affine(res_m, 0, minx, 0, -res_m, maxy)
    return Grid(crs.to_wkt(), tuple(t)[:6], w, h)


class RemoteImage:
    """Lazy handle on one HiRISE RED product."""

    def __init__(self, product_id: str, pds_path: str | None = None, prefer: str = "cog"):
        self.product_id = product_id
        self.pds_path = pds_path
        self.prefer = prefer
        self._ds = None
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        if self.prefer == "jp2" and self.pds_path:
            return pds_jp2_url(self.pds_path)
        return cog_url(self.product_id)

    def _open(self):
        if self._ds is None:
            with rasterio.Env(**GDAL_ENV):
                _limiter.acquire()
                try:
                    self._ds = rasterio.open(f"/vsicurl/{self.url}")
                except rasterio.errors.RasterioIOError:
                    if self.prefer == "cog" and self.pds_path:
                        log.warning(f"COG unavailable for {self.product_id}; falling back to PDS JP2")
                        self.prefer = "jp2"
                        self._ds = rasterio.open(f"/vsicurl/{self.url}")
                    else:
                        raise
        return self._ds

    def info(self) -> dict:
        ds = self._open()
        return {
            "product_id": self.product_id,
            "url": self.url,
            "width": ds.width,
            "height": ds.height,
            "res": ds.res,
            "crs": ds.crs.to_wkt(),
            "bounds": tuple(ds.bounds),
            "scale": ds.scales[0],
            "offset": ds.offsets[0],
            "overviews": ds.overviews(1),
        }

    def read_to_grid(self, grid: Grid, resampling: Resampling = Resampling.bilinear) -> tuple[np.ndarray, np.ndarray]:
        """Return (I/F float32 array, valid mask) resampled onto ``grid``.

        Reads only the source window covering the grid, decimated to roughly the
        grid resolution so that COG overviews are used for coarse grids.
        """
        t0 = time.monotonic()
        with self._lock, rasterio.Env(**GDAL_ENV):
            ds = self._open()
            left, top = grid.affine * (0, 0)
            right, bottom = grid.affine * (grid.width, grid.height)
            sb = transform_bounds(grid.crs, ds.crs, left, bottom, right, top, densify_pts=21)
            win = from_bounds(*sb, transform=ds.transform)
            # source ground resolution (m/px) along each axis, measured in the grid CRS
            src_px_m = math.sqrt(((right - left) / max(win.width, 1)) * ((top - bottom) / max(win.height, 1)))
            pad = 4
            win = Window(int(math.floor(win.col_off)) - pad, int(math.floor(win.row_off)) - pad,
                         int(math.ceil(win.width)) + 2 * pad, int(math.ceil(win.height)) + 2 * pad)
            full = Window(0, 0, ds.width, ds.height)
            try:
                win_c = win.intersection(full)
            except rasterio.errors.WindowError:
                return np.zeros((grid.height, grid.width), np.float32), np.zeros((grid.height, grid.width), bool)
            decim = max(1.0, (grid.res / max(src_px_m, 1e-6)) / 1.5)
            out_h = max(1, int(round(win_c.height / decim)))
            out_w = max(1, int(round(win_c.width / decim)))
            _limiter.acquire()
            try:
                src = ds.read(1, window=win_c, out_shape=(out_h, out_w), resampling=Resampling.average if decim > 1.5 else Resampling.nearest)
            except Exception:
                with ReadStats.lock:
                    ReadStats.failures += 1
                raise
            src_t = ds.window_transform(win_c) * Affine.scale(win_c.width / out_w, win_c.height / out_h)
            scale, offset = ds.scales[0], ds.offsets[0]
            crs = ds.crs
        dst = np.zeros((grid.height, grid.width), np.float32)
        srcf = src.astype(np.float32)
        valid_src = src > 0
        srcf[~valid_src] = np.nan
        reproject(srcf, dst, src_transform=src_t, src_crs=crs, dst_transform=grid.affine, dst_crs=grid.crs,
                  resampling=resampling, src_nodata=np.nan, dst_nodata=np.nan)
        valid = np.isfinite(dst) & (dst > 0)
        out = np.where(valid, dst * scale + offset, 0).astype(np.float32)
        with ReadStats.lock:
            ReadStats.reads += 1
            ReadStats.pixels += int(src.size)
            ReadStats.seconds += time.monotonic() - t0
        return out, valid

    def close(self) -> None:
        if self._ds is not None:
            self._ds.close()
            self._ds = None


# ---------------------------------------------------------------------------
# Disk cache for resampled grids (bounded, LRU by access time)
# ---------------------------------------------------------------------------

def cache_path(product_id: str, grid: Grid) -> Path:
    return settings.cache_dir / "grids" / f"{product_id}_{grid.key()}.npz"


def read_cached(img: RemoteImage, grid: Grid, use_cache: bool = True) -> tuple[np.ndarray, np.ndarray]:
    p = cache_path(img.product_id, grid)
    if use_cache and p.exists():
        try:
            z = np.load(p)
            p.touch()
            with ReadStats.lock:
                ReadStats.cache_hits += 1
            return z["img"].astype(np.float32), z["valid"]
        except Exception:
            p.unlink(missing_ok=True)
    arr, valid = img.read_to_grid(grid)
    if use_cache:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, img=arr.astype(np.float16), valid=valid)
        tmp.rename(p)
        enforce_cache_budget()
    return arr, valid


def read_tiled(img: RemoteImage, grid: Grid, tile: int | None = None, use_cache: bool = True,
               progress=None) -> tuple[np.ndarray, np.ndarray]:
    """Read a large grid tile-by-tile (bounded memory per request, resumable via cache)."""
    tile = tile or settings.tile_px * 2
    out = np.zeros((grid.height, grid.width), np.float32)
    valid = np.zeros((grid.height, grid.width), bool)
    tiles = [(x, y) for y in range(0, grid.height, tile) for x in range(0, grid.width, tile)]
    for i, (x, y) in enumerate(tiles):
        w, h = min(tile, grid.width - x), min(tile, grid.height - y)
        a, v = read_cached(img, grid.subgrid(x, y, w, h), use_cache)
        out[y:y + h, x:x + w] = a
        valid[y:y + h, x:x + w] = v
        if progress:
            progress((i + 1) / len(tiles))
    return out, valid


def cache_size_bytes() -> int:
    d = settings.cache_dir
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) if d.exists() else 0


def enforce_cache_budget() -> int:
    """Delete least-recently-used cache files beyond the configured budget."""
    d = settings.cache_dir
    if not d.exists():
        return 0
    files = sorted((p for p in d.rglob("*.npz") if p.is_file()), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    budget = settings.cache_budget_mb * 1024 * 1024
    removed = 0
    while files and total > budget:
        p = files.pop(0)
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
        removed += 1
    return removed


# ---------------------------------------------------------------------------
# Input quality control
# ---------------------------------------------------------------------------

QC_MIN_SNR = 2.0


def structure_snr(img: np.ndarray, valid: np.ndarray) -> float:
    """Band-limited structure-to-noise ratio of an image.

    Noise σ from Immerkær's (1996) Laplacian estimator; structure σ from a
    difference-of-Gaussians band (2–20 px). Measured at a fixed 0.5 m/px so
    that values are comparable between products. Real HiRISE terrain gives
    ≳4.5; images acquired through the 2007 global dust storm give ≈1.
    """
    import cv2

    if valid.sum() < 1000:
        return 0.0
    a = np.where(valid, img, np.median(img[valid])).astype(np.float32)
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    lap = cv2.filter2D(a, -1, k)
    m = cv2.erode(valid.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    if m.sum() < 500:
        return 0.0
    sn = math.sqrt(math.pi / 2) / 6 * float(np.mean(np.abs(lap[m])))
    band = cv2.GaussianBlur(a, (0, 0), 2) - cv2.GaussianBlur(a, (0, 0), 20)
    return float(band[m].std() / (sn + 1e-12))


def input_quality(img: RemoteImage, center_lat: float, center_lon: float, half_m: float = 200.0) -> dict:
    g = make_grid(center_lat, center_lon, half_m, half_m, 0.5)
    a, v = read_cached(img, g)
    snr = structure_snr(a, v)
    return {"product_id": img.product_id, "structure_snr": round(snr, 2), "valid_fraction": float(v.mean()),
            "usable": bool(snr >= QC_MIN_SNR and v.mean() > 0.2)}


_cog_avail: dict[str, bool] = {}


def cog_available(product_id: str) -> bool:
    """HEAD check for the USGS COG (new HiRISE releases appear in the ARD bucket with a lag)."""
    if product_id not in _cog_avail:
        import httpx

        try:
            _limiter.acquire()
            r = httpx.head(cog_url(product_id), timeout=20)
            _cog_avail[product_id] = r.status_code == 200
        except Exception:
            return False
    return _cog_avail[product_id]
