"""
Plot traces for user galaxy catalogs and their CATRED matches.

Traces are found again by name prefix (TraceRegistry) and carry ``meta``
({"kind", "catalog_id", ...}) so callbacks and the Aladin overlay can tell which
catalog a trace belongs to without parsing its name.
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd  # type: ignore[import]
import plotly.graph_objs as go  # type: ignore[import]

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

# Plotly marker symbol -> (dropdown label, Aladin Lite shape)
SYMBOLS = {
    "diamond": ("Diamond", "rhomb"),
    "square": ("Square", "square"),
    "circle": ("Circle", "circle"),
    "triangle-up": ("Triangle", "triangle"),
    "cross": ("Plus", "plus"),
    "x": ("Cross", "cross"),
}

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
)


def catalog_trace_name(spec) -> str:
    return f"{CATALOG_PREFIX}{spec.name}"


def match_trace_name(spec) -> str:
    return f"{MATCH_PREFIX}{spec.name}"


def trace_meta(trace) -> dict:
    """``meta`` of a trace given as dict or Plotly object ({} when absent)."""
    meta = trace.get("meta") if isinstance(trace, dict) else getattr(trace, "meta", None)
    return meta if isinstance(meta, dict) else {}


def _format(values: pd.Series) -> np.ndarray:
    """Values as hover strings: 4 decimals for floats, plain otherwise, blank for missing."""
    if pd.api.types.is_float_dtype(values):
        return np.array(["" if not np.isfinite(v) else f"{v:.4f}" for v in values], dtype=object)
    return np.array(["" if pd.isna(v) else str(v) for v in values], dtype=object)


def hover_texts(spec, df: pd.DataFrame) -> list:
    """One hover string per row: name, position, mapped roles, then hover columns."""
    from cluster_visualization.src.data.galaxy_catalog import GalaxyCatalog

    lines = [("RA", _format(df["RA"])), ("Dec", _format(df["DEC"]))]
    lines += [(label, _format(df[role])) for role, label in _HOVER_LABELS if role in df.columns]
    for column in spec.hover_columns:
        name = GalaxyCatalog.hover_name(column)
        if name in df.columns:
            lines.append((column, _format(df[name])))
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
    spec, df: pd.DataFrame, total: Optional[int] = None, windowed: bool = False
):
    """Marker trace for a catalog's rows (``total``: rows in the area before thinning)."""
    name = catalog_trace_name(spec)
    if total is not None and total > len(df):
        name += f" ({len(df):,} of {total:,} here)"
    return go.Scattergl(
        x=df["RA"].to_numpy(),
        y=df["DEC"].to_numpy(),
        mode="markers",
        marker=dict(
            size=7, symbol=spec.symbol, color=spec.color, line=dict(width=1, color="black")
        ),
        name=name,
        text=hover_texts(spec, df),
        # Row of each marker in the loaded catalog, so a click finds its galaxy
        customdata=df.index.to_numpy(),
        hoverinfo="text",
        showlegend=True,
        meta={
            "kind": KIND_CATALOG,
            "catalog_id": spec.id,
            "label": spec.name,
            "color": spec.color,
            "shape": SYMBOLS.get(spec.symbol, ("", "rhomb"))[1],
            "windowed": windowed,
        },
    )


def build_match_trace(spec, ra, dec, text):
    """CATRED sources matched to a catalog: hollow squares in the catalog's colour."""
    return go.Scattergl(
        x=ra,
        y=dec,
        mode="markers",
        marker=dict(
            size=9,
            symbol="square",
            color="rgba(0, 0, 0, 0)",
            line=dict(width=1.5, color=spec.color),
        ),
        name=match_trace_name(spec),
        text=text,
        hoverinfo="text",
        showlegend=True,
        meta={
            "kind": KIND_MATCH,
            "catalog_id": spec.id,
            "label": f"CATRED near {spec.name}",
            "color": spec.color,
            "shape": "square",
        },
    )
