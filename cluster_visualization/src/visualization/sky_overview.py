"""Globe overview of the sky: an orthographic projection showing filtered cluster
density as HEALPix cells plus neutral CL-tile outlines.

Nothing per cluster is sent: the density is aggregated on the server into at most
``globe_max_cells`` visible cells, so the globe stays light for any catalog size.
Sky longitude is drawn as lon = -RA, so RA increases to the left as on the sky.
"""

import math
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import plotly.graph_objects as go

GLOBE_SETTINGS = {
    "nside_max": 1024,
    "globe_max_cells": 3000,
    # Field of view (deg) below which zooming the globe hands over to the 2-D map,
    # and above which zooming the map out hands back to the globe
    "map_enter_fov": 8.0,
    "globe_enter_fov": 15.0,
}
# globe_enter_fov stays at least this factor above map_enter_fov, so the views never flip-flop
FOV_HYSTERESIS = 1.5

# Coarsest cells drawn (nside 8 = 7.3 deg cells)
MIN_NSIDE = 8
# The query disc is a little wider than the visible disc so small rotations need no request
VIEW_RADIUS_MARGIN = 1.2

DENSITY_TRACE = "Cluster density"

# Same ramp as the 2-D map's density grid (TraceCreator.DENSITY_COLORSCALE)
DENSITY_COLORSCALE = [[0, "rgba(43,87,151,0.15)"], [1, "rgba(43,87,151,0.95)"]]


def configure_globe(
    nside_max: Optional[int] = None,
    globe_max_cells: Optional[int] = None,
    map_enter_fov: Optional[float] = None,
    globe_enter_fov: Optional[float] = None,
) -> None:
    """Set the globe settings (config.ini [view]); values are rounded to valid ones."""
    if nside_max is not None:
        nside = 2 ** int(round(math.log2(max(MIN_NSIDE, min(int(nside_max), 8192)))))
        GLOBE_SETTINGS["nside_max"] = nside
    if globe_max_cells is not None:
        GLOBE_SETTINGS["globe_max_cells"] = max(100, int(globe_max_cells))
    if map_enter_fov is not None:
        GLOBE_SETTINGS["map_enter_fov"] = min(max(float(map_enter_fov), 0.1), 90.0)
    if globe_enter_fov is not None:
        GLOBE_SETTINGS["globe_enter_fov"] = float(globe_enter_fov)
    GLOBE_SETTINGS["globe_enter_fov"] = min(180.0, max(
        GLOBE_SETTINGS["globe_enter_fov"], GLOBE_SETTINGS["map_enter_fov"] * FOV_HYSTERESIS
    ))


def fov_for_scale(scale: float) -> float:
    """Full field of view (deg) of the orthographic globe at a projection scale
    (whole hemisphere, 180 deg, at scale <= 1). Mirrored in the browser handoff."""
    scale = float(scale or 1.0)
    return 180.0 if scale <= 1.0 else 2.0 * math.degrees(math.asin(1.0 / scale))


def scale_for_fov(fov: float) -> float:
    """Inverse of fov_for_scale."""
    fov = float(fov)
    return 1.0 if fov >= 180.0 else 1.0 / math.sin(math.radians(max(fov, 1e-3) / 2.0))


def _healpy():
    # Imported on first use: healpy is slow to import on network filesystems
    import healpy

    return healpy


# ----------------------------------------------------------------------------
# Resolution and visibility
# ----------------------------------------------------------------------------
def view_radius_deg(scale: float) -> float:
    """Angular radius (deg) of the sky visible at an orthographic projection scale."""
    scale = max(float(scale or 1.0), 1.0)
    return min(90.0, math.degrees(math.asin(1.0 / scale)) * VIEW_RADIUS_MARGIN)


def choose_nside(scale: float, nside_max: Optional[int] = None, max_cells: Optional[int] = None) -> int:
    """Finest power-of-two nside whose cells covering the visible disc stay within
    ``max_cells`` (a full disc of radius r holds 6 nside^2 (1 - cos r) cells).

    Mirrored in the browser's globe tracker (sky_overview_callbacks.py).
    """
    nside_max = int(nside_max or GLOBE_SETTINGS["nside_max"])
    max_cells = int(max_cells or GLOBE_SETTINGS["globe_max_cells"])
    frac = 1.0 - math.cos(math.radians(view_radius_deg(scale)))
    limit = math.sqrt(max_cells / (6.0 * frac))
    nside = 2 ** int(math.floor(math.log2(max(limit, 1.0))))
    return int(min(max(nside, MIN_NSIDE), nside_max))


def healpix_pixels(ra: np.ndarray, dec: np.ndarray, nside: int) -> np.ndarray:
    """NESTED HEALPix pixel of each position at ``nside`` (int64; -1 where not finite)."""
    ra = np.asarray(ra, dtype=float)
    dec = np.asarray(dec, dtype=float)
    out = np.full(len(ra), -1, dtype=np.int64)
    ok = np.isfinite(ra) & np.isfinite(dec)
    if ok.any():
        out[ok] = _healpy().ang2pix(int(nside), ra[ok], dec[ok], nest=True, lonlat=True)
    return out


def coarsen(pixels: np.ndarray, nside_from: int, nside_to: int) -> np.ndarray:
    """NESTED pixels at nside_from mapped to their parents at nside_to (<= nside_from)."""
    shift = 2 * int(round(math.log2(int(nside_from) // int(nside_to))))
    return np.asarray(pixels, dtype=np.int64) >> shift


def hpx_counts(pixels: np.ndarray, nside_from: int, nside_to: int) -> Tuple[np.ndarray, np.ndarray]:
    """Non-empty pixels at nside_to and their counts, from fine NESTED pixels."""
    pix, counts = np.unique(coarsen(pixels, nside_from, nside_to), return_counts=True)
    return pix, counts


def normalize_view(view: Dict[str, float]) -> Dict[str, float]:
    """View with lat in [-90, 90] and lon in [-180, 180).

    Plotly does not bound the orthographic rotation: dragging the globe over a pole,
    or a map -> globe handoff from a map scrolled past Dec +-90, gives lat outside
    +-90, which healpy rejects. Past a pole the centre is the same point as lat
    folded back with lon on the other side (lat 100 = lat 80 at lon + 180).
    """
    lon, lat = float(view["lon"]), float(view["lat"])
    lat = (lat + 180.0) % 360.0 - 180.0  # [-180, 180)
    if lat > 90.0:
        lat, lon = 180.0 - lat, lon + 180.0
    elif lat < -90.0:
        lat, lon = -180.0 - lat, lon + 180.0
    lon = (lon + 180.0) % 360.0 - 180.0
    return {**view, "lon": lon, "lat": lat}


def visible_pixels(nside: int, rot_lon: float, rot_lat: float, scale: float) -> np.ndarray:
    """NESTED pixels within the (slightly widened) visible disc around the view centre.

    rot_lon / rot_lat are the projection rotation, i.e. the centre at lon = -RA.
    """
    hp = _healpy()
    vec = hp.ang2vec(-float(rot_lon) % 360.0, float(rot_lat), lonlat=True)
    radius = math.radians(view_radius_deg(scale))
    return np.asarray(hp.query_disc(int(nside), vec, radius, inclusive=True, nest=True), dtype=np.int64)


# ----------------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------------
def _clockwise_ring(lon: np.ndarray, lat: np.ndarray) -> List[List[float]]:
    """Closed ring, clockwise in (lon, lat): d3-geo (Plotly geo) fills the smaller
    side of a clockwise ring; a counter-clockwise ring would fill the rest of the sphere."""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    # Unwrap relative to the first vertex so cells crossing lon +-180 stay compact
    lon = lon[0] + (lon - lon[0] + 180.0) % 360.0 - 180.0
    area2 = np.sum(lon * np.roll(lat, -1) - np.roll(lon, -1) * lat)
    if area2 > 0:  # counter-clockwise
        lon, lat = lon[::-1], lat[::-1]
    ring = np.round(np.column_stack([lon, lat]), 4).tolist()
    ring.append(ring[0])
    return ring


def cell_geojson(pixels: Sequence[int], nside: int) -> Dict[str, Any]:
    """GeoJSON FeatureCollection of HEALPix cells (feature id = pixel), lon = -RA."""
    hp = _healpy()
    pixels = np.asarray(pixels, dtype=np.int64)
    features = []
    if len(pixels):
        # Coarse cells have visibly curved edges: sample them more finely
        step = 1 if nside >= 64 else 4
        bounds = np.asarray(hp.boundaries(int(nside), pixels, step=step, nest=True))
        if bounds.ndim == 2:
            bounds = bounds[None, ...]
        for pix, b in zip(pixels.tolist(), bounds):
            ra, dec = hp.vec2ang(b.T, lonlat=True)
            features.append({
                "type": "Feature",
                "id": str(pix),
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [_clockwise_ring(-ra, dec)]},
            })
    return {"type": "FeatureCollection", "features": features}


def _circular_mean_deg(values: np.ndarray) -> float:
    rad = np.radians(np.asarray(values, dtype=float))
    return float(np.degrees(np.arctan2(np.nanmean(np.sin(rad)), np.nanmean(np.cos(rad)))) % 360.0)


def _extent_deg(ra: np.ndarray, dec: np.ndarray) -> Tuple[float, float, float]:
    """Catalog centre (RA, Dec) and angular radius (deg) holding 99% of the positions."""
    ra = np.asarray(ra, dtype=float)
    dec = np.asarray(dec, dtype=float)
    ok = np.isfinite(ra) & np.isfinite(dec)
    if not ok.any():
        return 0.0, 0.0, 0.0
    ra, dec = ra[ok], dec[ok]
    ra_c = _circular_mean_deg(ra)
    dec_c = float(np.clip(np.mean(dec), -89.0, 89.0))
    r1, d1, r2, d2 = map(np.radians, (ra, dec, ra_c, dec_c))
    cosd = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    radius = float(np.degrees(np.arccos(np.clip(np.percentile(cosd, 1), -1, 1))))
    return ra_c, dec_c, radius


def catalog_span_deg(data: Dict[str, Any]) -> float:
    """Angular diameter (deg) of the merged catalog; cached on ``data``. The browser
    starts on the globe when this exceeds globe_enter_fov."""
    merged = data.get("data_detcluster_mergedcat")
    cached = data.get("_catalog_span")
    if cached is not None and cached[0] is merged:
        return cached[1]
    span = 0.0
    if merged is not None and len(merged):
        span = 2.0 * _extent_deg(merged["RIGHT_ASCENSION_CLUSTER"], merged["DECLINATION_CLUSTER"])[2]
    data["_catalog_span"] = (merged, round(span, 3))
    return round(span, 3)


def default_view(ra: np.ndarray, dec: np.ndarray) -> Dict[str, float]:
    """Rotation centred on the catalog (lon = -RA) and a scale that fits nearly all of it."""
    ok = np.isfinite(np.asarray(ra, dtype=float)) & np.isfinite(np.asarray(dec, dtype=float))
    if not ok.any():
        return {"lon": 0.0, "lat": 0.0, "scale": 1.0}
    ra_c, dec_c, extent = _extent_deg(ra, dec)
    extent = max(extent * 1.3, 2.0)
    scale = 1.0 if extent >= 90.0 else 1.0 / math.sin(math.radians(extent))
    lon = (-ra_c + 180.0) % 360.0 - 180.0
    return {"lon": round(lon, 4), "lat": round(dec_c, 4), "scale": round(min(scale, 60.0), 3)}


# ----------------------------------------------------------------------------
# Traces
# ----------------------------------------------------------------------------
def density_trace(pixels: np.ndarray, counts: np.ndarray, nside: int, colorscale=None) -> go.Choropleth:
    """One Choropleth of HEALPix cells coloured by cluster count, styled like the
    2-D map's density grid (same colour ramp, linear counts)."""
    hp = _healpy()
    pixels = np.asarray(pixels, dtype=np.int64)
    counts = np.asarray(counts, dtype=float)
    if len(pixels):
        ra, dec = hp.pix2ang(int(nside), pixels, nest=True, lonlat=True)
    else:
        ra = dec = np.zeros(0)
    return go.Choropleth(
        geojson=cell_geojson(pixels, nside),
        locations=[str(p) for p in pixels.tolist()],
        z=counts,
        zmin=0.0,
        customdata=np.column_stack([ra, dec, counts]).astype(np.float32),
        colorscale=colorscale or DENSITY_COLORSCALE,
        marker=dict(line=dict(width=0)),
        colorbar=dict(title=dict(text="Clusters"), thickness=10, len=0.5),
        hovertemplate=(
            "RA %{customdata[0]:.2f}°, Dec %{customdata[1]:.2f}°<br>"
            "%{customdata[2]:.0f} clusters<extra>" + f"Cell (nside {int(nside)})" + "</extra>"
        ),
        name=DENSITY_TRACE,
        showlegend=False,
    )


def _tile_label(tile_id) -> str:
    try:
        return str(int(tile_id))
    except (TypeError, ValueError):
        return str(tile_id)


_CORE_TEXT = re.compile(r"^Tile (\S+) - CORE Polygon$")


def _with_counts(text, counts_by_tile: Dict[str, int]):
    """Add the filtered cluster count to "Tile N - CORE Polygon" hover texts."""
    def one(t):
        m = _CORE_TEXT.match(t) if isinstance(t, str) else None
        if not m:
            return t
        return f"{t}<br>{counts_by_tile.get(_tile_label(m.group(1)), 0):,} clusters"

    if isinstance(text, (list, tuple, np.ndarray)):
        return [one(t) for t in text]
    return one(text)


def _to_geo(trace, counts_by_tile: Dict[str, int]) -> go.Scattergeo:
    """A 2-D map outline trace (RA on x) as the same-styled Scattergeo (lon = -RA)."""
    line = trace.line
    return go.Scattergeo(
        lon=-np.asarray(trace.x, dtype=float),
        lat=np.asarray(trace.y, dtype=float),
        mode="lines",
        line=dict(color=line.color, width=line.width, dash=line.dash),
        text=_with_counts(trace.text, counts_by_tile),
        hoverinfo=trace.hoverinfo or "text",
        name=trace.name,
        showlegend=False,
    )


def tile_traces(data: Dict[str, Any], trace_creator, counts_by_tile: Dict[str, int]) -> List[go.Scattergeo]:
    """CL-tile CORE outlines in their per-tile colours, as the 2-D map draws them
    (same TraceCreator methods), redrawn on the globe. LEV1, MER tiles and fills
    stay on the map."""
    polygons: List = []
    seen = set()
    for key, value in (data.get("data_detcluster_by_cltile") or {}).items():
        if not isinstance(value, dict) or not value.get("cltiledef_file"):
            continue
        tile_id = value.get("tile_id", key)
        if _tile_label(tile_id) in seen:  # one entry per algorithm: draw each tile once
            continue
        seen.add(_tile_label(tile_id))
        try:
            trace_creator._create_cltile_polygons(
                polygons, data, tile_id, value, show_polygons=False, show_mer_tiles=False
            )
        except Exception as e:
            print(f"Debug: globe - no polygons for tile {tile_id}: {e}")
    core = [t for t in polygons if "CORE" in (t.name or "")]
    return [_to_geo(t, counts_by_tile) for t in trace_creator._merge_polygon_traces(core)]


# ----------------------------------------------------------------------------
# Figure
# ----------------------------------------------------------------------------
def build_sky_overview(
    data: Dict[str, Any],
    trace_creator,
    filter_kw: Dict[str, Any],
    view: Optional[Dict[str, float]] = None,
    matching_clusters: bool = False,
    uirevision: str = "globe",
) -> Tuple[go.Figure, Dict[str, Any]]:
    """Globe figure for the filtered catalog and a summary dict (nside, cells, timing).

    ``view`` is the browser's current {lon, lat, scale}; without it the globe is
    centred on the catalog and scaled to fit it. The layout always carries the
    catalog-fitting view; ``uirevision`` keeps the user's rotation/zoom over it.
    """
    _t0 = time.perf_counter()
    nside_max = GLOBE_SETTINGS["nside_max"]
    rows = trace_creator.selected_clusters(data, matching_clusters=matching_clusters, **filter_kw)

    merged = data["data_detcluster_mergedcat"]
    initial = default_view(merged["RIGHT_ASCENSION_CLUSTER"], merged["DECLINATION_CLUSTER"])
    if not (view and all(view.get(k) is not None for k in ("lon", "lat", "scale"))):
        view = initial
    # The requested view is the browser's current one (after a user zoom or a map -> globe
    # handoff): put it in the layout so the new figure keeps the globe where it is
    view = normalize_view({k: float(view[k]) for k in ("lon", "lat", "scale")})

    fine = trace_creator.row_column(
        data, rows, f"hpx{nside_max}",
        lambda r: healpix_pixels(r["RIGHT_ASCENSION_CLUSTER"], r["DECLINATION_CLUSTER"], nside_max),
    )
    nside = choose_nside(view["scale"], nside_max)
    pix, counts = hpx_counts(fine[fine >= 0], nside_max, nside)
    keep = np.isin(pix, visible_pixels(nside, view["lon"], view["lat"], view["scale"]))
    pix, counts = pix[keep], counts[keep]

    counts_by_tile: Dict[str, int] = {}
    if len(rows) and data.get("data_detcluster_by_cltile"):
        ids, n = np.unique(np.asarray(trace_creator.tile_ids_for_rows(data, rows), dtype=str),
                           return_counts=True)
        counts_by_tile = {_tile_label(i): int(c) for i, c in zip(ids.tolist(), n.tolist())}

    density = density_trace(pix, counts, nside, getattr(trace_creator, "DENSITY_COLORSCALE", None))
    tiles = tile_traces(data, trace_creator, counts_by_tile)
    fig = go.Figure(data=[density, *tiles])
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        uirevision=uirevision,
        # The browser's globe tracker compares the live view with `view` / `nside`
        # (what these cells were computed for) to decide when to ask again
        meta={"globe": True, "nside": nside, "nside_max": nside_max,
              "max_cells": GLOBE_SETTINGS["globe_max_cells"], "uirevision": uirevision,
              "view": view},
        geo=dict(
            projection=dict(
                type="orthographic",
                rotation=dict(lon=view["lon"], lat=view["lat"]),
                scale=view["scale"],
            ),
            showland=False,
            showocean=False,
            showcoastlines=False,
            showcountries=False,
            showlakes=False,
            showrivers=False,
            showframe=False,
            bgcolor="rgba(0,0,0,0)",
            lonaxis=dict(showgrid=True, dtick=15, gridcolor="rgba(128,128,128,0.25)", gridwidth=0.5),
            lataxis=dict(showgrid=True, dtick=10, gridcolor="rgba(128,128,128,0.25)", gridwidth=0.5),
        ),
    )
    summary = {
        "nside": nside,
        "cells": int(len(pix)),
        "clusters": int(len(rows)),
        "seconds": time.perf_counter() - _t0,
    }
    return fig, summary
