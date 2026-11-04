"""Mars geometry helpers: footprints, local equal-area projections, areas.

All planetocentric coordinates use the IAU 2015 Mars sphere (R = 3,396,190 m),
matching the USGS HiRISE COGs. Longitudes are positive East; functions accept
either 0..360 or -180..180 and normalise as required.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import transform as shp_transform

MARS_RADIUS_M = 3_396_190.0


def lon180(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0


def lon360(lon: float) -> float:
    return lon % 360.0


MARS_GEOG_WKT = (
    'GEOGCS["Mars (2015) - Sphere / Ocentric",DATUM["Mars (2015) - Sphere",'
    'SPHEROID["Mars (2015) - Sphere",3396190,0]],PRIMEM["Reference Meridian",0],'
    'UNIT["degree",0.0174532925199433]]'
)


@lru_cache(maxsize=256)
def local_laea(lat: float, lon: float) -> CRS:
    """Lambert azimuthal equal-area projection on the Mars sphere centred on (lat, lon)."""
    lat = round(lat, 4)
    lon = round(lon180(lon), 4)
    wkt = (
        f'PROJCS["Mars LAEA local ({lat:.4f},{lon:.4f})",{MARS_GEOG_WKT},'
        'PROJECTION["Lambert_Azimuthal_Equal_Area"],'
        f'PARAMETER["latitude_of_center",{lat}],PARAMETER["longitude_of_center",{lon}],'
        'PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1]]'
    )
    return CRS.from_wkt(wkt)


@lru_cache(maxsize=1)
def mars_geographic() -> CRS:
    return CRS.from_wkt(MARS_GEOG_WKT)


@lru_cache(maxsize=256)
def _transformer(src_wkt: str, dst_wkt: str) -> Transformer:
    return Transformer.from_crs(CRS.from_wkt(src_wkt), CRS.from_wkt(dst_wkt), always_xy=True)


def to_local(crs: CRS) -> Transformer:
    return _transformer(mars_geographic().to_wkt(), crs.to_wkt())


def from_local(crs: CRS) -> Transformer:
    return _transformer(crs.to_wkt(), mars_geographic().to_wkt())


def footprint(obs: dict) -> Polygon:
    """Lon/lat polygon (lon possibly > 180 for unwrapped footprints) from index corners."""
    pts = [(obs[f"c{i}_lon"], obs[f"c{i}_lat"]) for i in range(1, 5)]
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.convex_hull  # corner order is not guaranteed to be ring order
    return poly


def _align_lon(poly: Polygon, ref_lon: float) -> Polygon:
    """Shift a lon/lat polygon by ±360 so it lies near ref_lon."""
    cx = poly.centroid.x
    shift = round((ref_lon - cx) / 360.0) * 360.0
    if shift == 0:
        return poly
    return shp_transform(lambda x, y, z=None: (x + shift, y), poly)


def project_polygon(poly: Polygon, crs: CRS) -> Polygon:
    t = to_local(crs)
    return shp_transform(lambda x, y, z=None: t.transform(x, y), poly)


@dataclass
class Overlap:
    area_km2: float
    frac_a: float
    frac_b: float
    polygon_lonlat: Polygon
    center_lat: float
    center_lon: float


def overlap(obs_a: dict, obs_b: dict) -> Overlap | None:
    pa = footprint(obs_a)
    pb = _align_lon(footprint(obs_b), pa.centroid.x)
    if not pa.intersects(pb):
        return None
    inter = pa.intersection(pb)
    if inter.is_empty or inter.area == 0:
        return None
    c = inter.centroid
    crs = local_laea(c.y, c.x)
    a_area = project_polygon(pa, crs).area
    b_area = project_polygon(pb, crs).area
    i_area = project_polygon(inter, crs).area
    return Overlap(
        area_km2=i_area / 1e6,
        frac_a=i_area / a_area if a_area else 0.0,
        frac_b=i_area / b_area if b_area else 0.0,
        polygon_lonlat=inter,  # type: ignore[arg-type]
        center_lat=c.y,
        center_lon=lon360(c.x),
    )


def point_in_footprint(obs: dict, lat: float, lon: float, margin_m: float = 0.0) -> bool:
    poly = footprint(obs)
    from shapely.geometry import Point

    p = _align_lon(Polygon([(lon, lat), (lon + 1e-9, lat), (lon, lat + 1e-9)]), poly.centroid.x).exterior.coords[0]
    crs = local_laea(lat, p[0])
    lp = project_polygon(poly, crs)
    return lp.buffer(-margin_m).contains(Point(0.0, 0.0)) if margin_m > 0 else lp.contains(Point(0.0, 0.0))


def angular_diff(a: float | None, b: float | None, period: float = 360.0) -> float | None:
    if a is None or b is None:
        return None
    d = abs(a - b) % period
    return min(d, period - d)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * MARS_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))
