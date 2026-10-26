"""
Plot traces for user galaxy and cluster catalogs, and their matches (CATRED sources
near galaxies; Euclid counterparts of external clusters).

Traces are found again by name prefix (TraceRegistry) and carry ``meta``
({"kind", "catalog_id", ...}) so callbacks and the Aladin overlay can tell which
catalog a trace belongs to without parsing its name.
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd  # type: ignore[import]
import plotly.graph_objs as go  # type: ignore[import]
from loguru import logger

from cluster_visualization.src.data import cluster_matcher

CATALOG_PREFIX = "Catalog: "
MATCH_PREFIX = "Catalog match: "
KIND_CATALOG = "catalog"
KIND_MATCH = "catalog_match"

# Markers drawn per catalog. Larger catalogs are drawn for the current view only
# (with a margin), thinned to this many points when the view still holds more.
# Every server callback that reads the figure sends it back over the SSH tunnel,
# so this keeps the figure small.
DISPLAY_MAX = 10_000
WINDOW_MARGIN = 0.5  # fraction of the view added on each side of a windowed catalog

# Marker shapes offered per catalog (Plotly symbol -> dropdown label). Open shapes are
# outlines in the catalog's colour, so markers of another catalog stay visible under them.
# The Aladin view draws the same shapes (see the Aladin overlay in ui_callbacks).
SYMBOLS = {
    "diamond": "Diamond",
    "circle": "Circle",
    "square": "Square",
    "triangle-up": "Triangle",
    "triangle-down": "Triangle down",
    "star": "Star",
    "hexagon": "Hexagon",
    "cross": "Plus",
    "x": "Cross",
    "circle-open": "Circle (open)",
    "square-open": "Square (open)",
    "diamond-open": "Diamond (open)",
    "triangle-up-open": "Triangle (open)",
    "star-open": "Star (open)",
    "hexagon-open": "Hexagon (open)",
}
# Marker sizes (px) offered per catalog: a larger open marker around a smaller filled one
# keeps two catalogs with the same galaxies apart
SIZES = {5: "Small", 7: "Medium", 10: "Large", 13: "X-large"}
DEFAULT_SIZE = 7
# Shapes given to new catalogs, the first one no other catalog uses
SYMBOL_CYCLE = (
    "diamond",
    "circle-open",
    "triangle-up",
    "square-open",
    "star",
    "hexagon-open",
    "triangle-down",
    "diamond-open",
    "circle",
    "star-open",
)
MATCH_SYMBOL, MATCH_SIZE = "square-open", 9
# Euclid counterparts of a cluster catalog: a ring around each matched external cluster
# (this much larger than the catalog's marker) and a line to each counterpart
CLUSTER_MATCH_SYMBOL, CLUSTER_MATCH_GROWTH = "circle-open", 8
# Opacity of catalog markers (sidebar slider): fainter markers keep the clusters drawn on
# top readable. CATRED matches stay opaque.
DEFAULT_OPACITY = 0.6


def marker_style(symbol: str, size: int, color: str) -> dict:
    """Plotly marker: open shapes are drawn in ``color``; filled ones get a black edge."""
    if symbol.endswith("-open"):
        return dict(size=size, symbol=symbol, color=color, line=dict(width=1.5, color=color))
    return dict(size=size, symbol=symbol, color=color, line=dict(width=1, color="black"))


# Hover label per role (RA/DEC are always shown first)
_HOVER_LABELS = (
    ("SOURCE_ID", "ID"),
    ("OBJECT_ID", "OBJECT_ID"),
    ("TILE_ID", "Tile"),
    ("SPEC_Z", "z_spec"),
    ("SPEC_Z_ERR", "z_spec err"),
    ("SPEC_Z_QUALITY", "z_spec flag"),
    ("PHOT_Z", "z_phot"),
    ("CLUSTER_ID", "Cluster ID"),
    ("Z", "z"),
    ("Z_ERR", "z err"),
    ("MASS", "Mass"),
    ("RICHNESS", "Richness"),
    ("SNR", "SNR"),
)
# Units not worth repeating on every hover line
_PLAIN_UNITS = {"", "deg", "degree", "degrees"}


def catalog_trace_name(spec) -> str:
    return f"{CATALOG_PREFIX}{spec.name}"


def match_trace_name(spec) -> str:
    return f"{MATCH_PREFIX}{spec.name}"


def trace_meta(trace) -> dict:
    """``meta`` of a trace given as dict or Plotly object ({} when absent)."""
    meta = trace.get("meta") if isinstance(trace, dict) else getattr(trace, "meta", None)
    return meta if isinstance(meta, dict) else {}


# Hover text of a missing value in cluster catalogs (galaxy catalogs leave the line out)
MISSING = "nan"


def _format(values: pd.Series, missing: str = "") -> np.ndarray:
    """Values as hover strings: 4 decimals for floats, plain otherwise, ``missing`` for missing."""
    if pd.api.types.is_float_dtype(values):
        return np.array(
            [missing if not np.isfinite(v) else f"{v:.4f}" for v in values], dtype=object
        )
    return np.array([missing if pd.isna(v) else str(v) for v in values], dtype=object)


def hover_texts(spec, df: pd.DataFrame) -> list:
    """One hover string per row: name, position, mapped roles, then hover columns.

    Cluster catalogs show a missing value as "nan", so every mapped column is listed for
    every cluster; galaxy catalogs leave missing values out.
    """
    from cluster_visualization.src.data.galaxy_catalog import CLUSTER, GalaxyCatalog

    missing = MISSING if getattr(spec, "kind", None) == CLUSTER else ""
    units = getattr(spec, "units", None) or {}
    lines = [("RA", _format(df["RA"], missing)), ("Dec", _format(df["DEC"], missing))]
    for role, label in _HOVER_LABELS:
        if role in df.columns:
            unit = units.get(role, "")
            if unit.strip().lower() not in _PLAIN_UNITS:
                label = f"{label} [{unit}]"
            lines.append((label, _format(df[role], missing)))
    for column in spec.hover_columns:
        name = GalaxyCatalog.hover_name(column)
        if name in df.columns:
            lines.append((column, _format(df[name], missing)))
    title = f"<b>{spec.name}</b>"
    return [
        "<br>".join(
            [title] + [f"{label}: {values[i]}" for label, values in lines if values[i] != ""]
        )
        for i in range(len(df))
    ]


def select_for_display(catalog, viewport: Optional[dict] = None) -> Tuple[pd.DataFrame, int, bool]:
    """(rows to draw, rows in the drawn area, windowed) for a catalog.

    Catalogs up to DISPLAY_MAX rows are drawn whole. Larger ones are cut to the
    viewport plus WINDOW_MARGIN on each side (whole sky without a viewport), then
    thinned to DISPLAY_MAX with a fixed seed so the same view draws the same points.
    """
    df = catalog.get_all()
    if df is None:
        return pd.DataFrame(columns=["RA", "DEC"]), 0, False
    if len(df) <= DISPLAY_MAX:
        return df, len(df), False
    if viewport is not None:
        dra = (viewport["ra_max"] - viewport["ra_min"]) * WINDOW_MARGIN
        ddec = (viewport["dec_max"] - viewport["dec_min"]) * WINDOW_MARGIN
        df = catalog.in_box(
            viewport["ra_min"] - dra,
            viewport["ra_max"] + dra,
            viewport["dec_min"] - ddec,
            viewport["dec_max"] + ddec,
        )
    total = len(df)
    if total > DISPLAY_MAX:
        df = df.sample(DISPLAY_MAX, random_state=0).sort_index()
    return df, total, True


def build_catalog_trace(
    spec,
    df: pd.DataFrame,
    total: Optional[int] = None,
    windowed: bool = False,
    opacity: float = DEFAULT_OPACITY,
):
    """Marker trace for a catalog's rows (``total``: rows in the area before thinning)."""
    name = catalog_trace_name(spec)
    if total is not None and total > len(df):
        name += f" ({len(df):,} of {total:,} here)"
    return go.Scattergl(
        x=df["RA"].to_numpy(),
        y=df["DEC"].to_numpy(),
        mode="markers",
        marker=dict(marker_style(spec.symbol, spec.size, spec.color), opacity=opacity),
        name=name,
        text=hover_texts(spec, df),
        # Row of each marker in the loaded catalog, so a click finds its galaxy
        customdata=df.index.to_numpy(),
        hoverinfo="text",
        showlegend=True,
        meta={
            "kind": KIND_CATALOG,
            "catalog_kind": spec.kind,
            "catalog_id": spec.id,
            "label": spec.name,
            # Marker style for the Aladin view
            "color": spec.color,
            "symbol": spec.symbol,
            "size": spec.size,
            "opacity": opacity,
            "windowed": windowed,
        },
    )


def build_match_trace(spec, ra, dec, text):
    """CATRED sources matched to a catalog: open squares in the catalog's colour."""
    return go.Scattergl(
        x=ra,
        y=dec,
        mode="markers",
        marker=marker_style(MATCH_SYMBOL, MATCH_SIZE, spec.color),
        name=match_trace_name(spec),
        text=text,
        hoverinfo="text",
        showlegend=True,
        meta={
            "kind": KIND_MATCH,
            "catalog_id": spec.id,
            "label": f"CATRED near {spec.name}",
            "color": spec.color,
            "symbol": MATCH_SYMBOL,
            "size": MATCH_SIZE,
        },
    )


# ---------------------------------------------------------------------------
# Cluster catalogs: Euclid counterparts
# ---------------------------------------------------------------------------


def cluster_match_name(spec, algorithm) -> str:
    return f"{MATCH_PREFIX}{spec.name} ↔ Euclid {algorithm}"


def _in_window(ra, dec, viewport, margin=WINDOW_MARGIN) -> np.ndarray:
    dra = (viewport["ra_max"] - viewport["ra_min"]) * margin
    ddec = (viewport["dec_max"] - viewport["dec_min"]) * margin
    return (
        (ra >= viewport["ra_min"] - dra)
        & (ra <= viewport["ra_max"] + dra)
        & (dec >= viewport["dec_min"] - ddec)
        & (dec <= viewport["dec_max"] + ddec)
    )


def _cluster_match_hover(spec, ext: pd.DataFrame, best: pd.DataFrame, merged, extra) -> list:
    """Hover of each ring: the external cluster, its nearest Euclid counterpart, the offsets."""
    texts = []
    for (_, pair), n_more in zip(best.iterrows(), extra):
        row = ext.loc[pair["EXT_ROW"]]
        title = row["SOURCE_ID"] if "SOURCE_ID" in ext.columns else f"#{int(pair['EXT_ROW'])}"
        lines = [
            f"<b>{title}</b> ({spec.name})",
            f"Euclid ID {pair['ID_UNIQUE_CLUSTER']}: {pair['SEP_ARCMIN']:.2f}′",
        ]
        z_euclid = float(merged["Z_CLUSTER"][int(pair["EUCLID_ROW"])])
        z_ext = float(row["Z"]) if "Z" in ext.columns else np.nan
        if np.isfinite(pair["DZ"]):
            lines[-1] += f", Δz/(1+z) {pair['DZ']:.3f}"
        else:
            lines[-1] += ", by position (no z)"
        lines.append(f"z {z_ext:.3f}, Euclid z {z_euclid:.3f}")  # NaN reads "nan"
        if n_more:
            lines.append(f"+{n_more} more Euclid cluster(s) within {spec.match_radius_arcmin:g}′")
        texts.append("<br>".join(lines))
    return texts


def build_cluster_match_traces(spec, matches, ext, merged, algorithm, viewport=None):
    """([links, rings], windowed): a line from each external cluster to each Euclid
    counterpart, and a ring on each matched external cluster with the nearest one on hover.

    More than DISPLAY_MAX pairs are cut to the viewport (plus margin) when there is one.
    """
    if len(matches) == 0:
        return [], False
    ext_row = matches["EXT_ROW"].to_numpy()
    euclid_row = matches["EUCLID_ROW"].to_numpy(dtype=np.int64)
    ext_ra = ext.loc[ext_row, "RA"].to_numpy(dtype=float)
    ext_dec = ext.loc[ext_row, "DEC"].to_numpy(dtype=float)
    windowed = False
    if len(matches) > DISPLAY_MAX and viewport is not None:
        keep = _in_window(ext_ra, ext_dec, viewport)
        matches, euclid_row = matches[keep], euclid_row[keep]
        ext_ra, ext_dec = ext_ra[keep], ext_dec[keep]
        windowed = True
    eu_ra = np.asarray(merged["RIGHT_ASCENSION_CLUSTER"], dtype=float)[euclid_row]
    eu_dec = np.asarray(merged["DECLINATION_CLUSTER"], dtype=float)[euclid_row]

    name = cluster_match_name(spec, algorithm)
    meta = {
        "kind": KIND_MATCH,
        "catalog_kind": spec.kind,
        "catalog_id": spec.id,
        "algorithm": algorithm,
        "label": f"Euclid counterparts of {spec.name}",
        "color": spec.color,
        "symbol": CLUSTER_MATCH_SYMBOL,
        "size": spec.size + CLUSTER_MATCH_GROWTH,
    }
    # One segment per pair, NaN-separated; a pair across RA 0/360 is not drawn
    wraps = np.abs(ext_ra - eu_ra) > 180
    gap = np.full(len(ext_ra), np.nan)
    xs = np.column_stack([np.where(wraps, np.nan, ext_ra), eu_ra, gap]).ravel()
    ys = np.column_stack([ext_dec, eu_dec, gap]).ravel()
    links = go.Scattergl(
        x=xs,
        y=ys,
        mode="lines",
        line=dict(color=spec.color, width=1.5),
        name=f"{name} (links)",
        legendgroup=name,
        hoverinfo="skip",
        showlegend=False,
        meta={**meta, "links": True},
    )

    best = matches[matches["BEST"].astype(bool)]
    extra = (matches.groupby("EXT_ROW").size() - 1).reindex(best["EXT_ROW"]).to_numpy()
    rings = go.Scattergl(
        x=ext.loc[best["EXT_ROW"], "RA"].to_numpy(dtype=float),
        y=ext.loc[best["EXT_ROW"], "DEC"].to_numpy(dtype=float),
        mode="markers",
        marker=marker_style(CLUSTER_MATCH_SYMBOL, spec.size + CLUSTER_MATCH_GROWTH, spec.color),
        name=name,
        legendgroup=name,
        text=_cluster_match_hover(spec, ext, best, merged, extra),
        hoverinfo="text",
        showlegend=True,
        meta=meta,
    )
    return [links, rings], windowed


def cluster_match_traces(catalog, data, viewport=None):
    """(traces, feedback line) of a cluster catalog's Euclid counterparts in ``data``
    (the merged catalog of the loaded algorithm, before filters)."""
    spec = catalog.spec
    matches = cluster_matcher.cached_matches(catalog, data)
    if matches is None:
        return [], f"{spec.name}: {catalog.status}"
    algorithm = data.get("algorithm")
    counts = cluster_matcher.match_summary(matches, len(catalog.df))
    note = (
        f"{spec.name}: {counts['matched']:,} of {counts['external']:,} matched ({algorithm}, "
        f"{spec.match_radius_arcmin:g}′, Δz/(1+z) ≤ {spec.match_dz:g}"
    )
    if counts["position_only"]:
        note += f"; {counts['position_only']:,} by position only"
    note += ")"
    traces, windowed = build_cluster_match_traces(
        spec, matches, catalog.df, data["data_detcluster_mergedcat"], algorithm, viewport
    )
    if windowed:
        note += "; links drawn for the current view"
    logger.info(note)
    return traces, note
