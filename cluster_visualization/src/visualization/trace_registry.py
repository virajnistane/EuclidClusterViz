"""
Centralized trace type registry and preservation utilities.

Single source of truth for trace identification, layer ordering,
and extraction/reassembly across all callbacks.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Callable, Optional

import plotly.graph_objs as go

# Name prefix of the cluster modal's HEALPix mask cutout traces. They are built
# like the sidebar's viewport mask (same names after the prefix) but form a
# separate layer with its own Hide/Clear controls.
CUTOUT_MASK_PREFIX = "Cutout "


class TraceType(Enum):
    """All known trace types in the visualization, ordered by layer."""
    POLYGON = auto()
    MOSAIC = auto()
    MASK_OVERLAY = auto()
    CATRED = auto()
    NED_SPECZ = auto()
    MEMBERS = auto()
    MATCHED_PAIR = auto()
    CLUSTER = auto()
    SELECTED_CLUSTER = auto()


@dataclass(frozen=True)
class TraceTypeSpec:
    """Specification for a trace type's identification and reconstruction."""
    name: str
    layer_order: int
    match: Callable[[dict], bool]
    reconstruct: Callable[[dict], object]


# ---------------------------------------------------------------------------
# Match helpers
# ---------------------------------------------------------------------------

def _get_trace_name(trace) -> str:
    if isinstance(trace, dict):
        return trace.get("name", "") or ""
    return getattr(trace, "name", "") or ""


def _name_startswith(trace, prefix: str) -> bool:
    return _get_trace_name(trace).startswith(prefix)


def _name_contains(trace, substring: str) -> bool:
    return substring in _get_trace_name(trace)


def _name_equals(trace, name: str) -> bool:
    return _get_trace_name(trace) == name


def _match_polygon(trace) -> bool:
    name = _get_trace_name(trace)
    return (
        ("LEV1" in name and "Tile" in name)
        or ("CORE" in name and "Tile" in name)
        or name.startswith("MER-Tile")
        or ("MerTile" in name and "Tile" in name)
    )


def _match_mosaic(trace) -> bool:
    return _name_contains(trace, "Mosaic")


def _match_mask_overlay(trace) -> bool:
    name = _get_trace_name(trace)
    if name.startswith(CUTOUT_MASK_PREFIX):
        name = name[len(CUTOUT_MASK_PREFIX):]
    return (
        "Mask overlay" in name
        or "Inverted mask" in name
        or name == "Mask Colorbar"
        or name == "Mask aladin moc"
        or name == "Inverted mask aladin moc"
    )


def _match_catred(trace) -> bool:
    return _name_startswith(trace, "CATRED")


def _match_ned_specz(trace) -> bool:
    return _name_startswith(trace, "NED Spec-z")


def _match_members(trace) -> bool:
    return _name_startswith(trace, "Members (ID")


def _match_matched_pair(trace) -> bool:
    return _name_equals(trace, "Matched Pair")


def _match_selected_cluster(trace) -> bool:
    return _name_equals(trace, "__selected_cluster__")


def _match_cluster(trace) -> bool:
    name = _get_trace_name(trace)
    return (
        "Merged" in name
        or "Unmerged" in name
        or "(Enhanced)" in name
        or "Cluster in Proximity" in name
    )


# ---------------------------------------------------------------------------
# Reconstruction helpers
# ---------------------------------------------------------------------------

def _reconstruct_mosaic(trace: dict):
    trace_type = trace.get("type", "image")
    if trace_type == "image":
        return go.Image(
            source=trace.get("source"),
            x0=trace.get("x0"),
            y0=trace.get("y0"),
            dx=trace.get("dx"),
            dy=trace.get("dy"),
            name=trace.get("name", "Mosaic Image"),
            opacity=trace.get("opacity", 1.0),
        )
    elif trace_type == "heatmap":
        return go.Heatmap(
            z=trace.get("z"),
            x=trace.get("x"),
            y=trace.get("y"),
            name=trace.get("name", "Mosaic Image"),
            opacity=trace.get("opacity", 1.0),
            colorscale=trace.get("colorscale", "gray"),
            showscale=trace.get("showscale", False),
        )
    return trace


def _reconstruct_mask_overlay(trace: dict):
    trace_type = trace.get("type", "scatter")
    name = trace.get("name", "")

    if trace_type == "scatter" or trace_type == "scattergl":
        if name == "Mask Colorbar":
            return go.Scatter(
                x=trace.get("x"),
                y=trace.get("y"),
                mode=trace.get("mode", "markers"),
                showlegend=trace.get("showlegend", False),
                hoverinfo=trace.get("hoverinfo", "skip"),
                name=name,
                marker=trace.get("marker", {}),
            )
        else:
            return go.Scatter(
                x=trace.get("x", []),
                y=trace.get("y", []),
                mode=trace.get("mode", "lines"),
                fill=trace.get("fill"),
                fillcolor=trace.get("fillcolor", "rgba(0,0,0,0)"),
                line=trace.get("line", {}),
                name=trace.get("name", "Mask overlay"),
                opacity=trace.get("opacity", 0.6),
                hoverinfo=trace.get("hoverinfo", "text"),
                showlegend=trace.get("showlegend", False),
                customdata=trace.get("customdata", None),
                text=trace.get("text", None),
                visible=trace.get("visible", True),
            )
    elif trace_type == "image":
        return go.Image(
            source=trace.get("source"),
            x0=trace.get("x0"),
            y0=trace.get("y0"),
            dx=trace.get("dx"),
            dy=trace.get("dy"),
            name=trace.get("name", "Mask overlay"),
            opacity=trace.get("opacity", 1.0),
        )
    elif trace_type == "heatmap":
        return go.Heatmap(
            z=trace.get("z"),
            x=trace.get("x"),
            y=trace.get("y"),
            name=trace.get("name", "Mask overlay"),
            opacity=trace.get("opacity", 0.6),
            colorscale=trace.get("colorscale", "viridis"),
            showscale=trace.get("showscale", False),
        )
    return trace


def _reconstruct_catred(trace: dict):
    return go.Scattergl(
        x=trace.get("x", []),
        y=trace.get("y", []),
        mode=trace.get("mode", "markers"),
        marker=trace.get("marker", {}),
        name=trace.get("name", "CATRED Data"),
        text=trace.get("text", []),
        customdata=trace.get("customdata", None),
        hovertemplate=trace.get("hovertemplate", None),
        hoverlabel=trace.get("hoverlabel", None),
        hoverinfo=trace.get("hoverinfo", "text"),
        legendgroup=trace.get("legendgroup", None),
        opacity=trace.get("opacity", None),
        showlegend=trace.get("showlegend", True),
        visible=trace.get("visible", True),
    )


def _reconstruct_ned_specz(trace: dict):
    return go.Scattergl(
        x=trace.get("x", []),
        y=trace.get("y", []),
        mode=trace.get("mode", "markers"),
        marker=trace.get("marker", {}),
        name=trace.get("name", "NED Spec-z Galaxies"),
        text=trace.get("text", []),
        customdata=trace.get("customdata", None),
        hovertemplate=trace.get("hovertemplate", None),
        hoverinfo=trace.get("hoverinfo", "text"),
        showlegend=trace.get("showlegend", True),
        visible=trace.get("visible", True),
    )


def _reconstruct_members(trace: dict):
    return go.Scattergl(
        x=trace.get("x", []),
        y=trace.get("y", []),
        mode=trace.get("mode", "markers"),
        marker=trace.get("marker", {}),
        name=trace.get("name", ""),
        customdata=trace.get("customdata", None),
        hovertemplate=trace.get("hovertemplate", None),
        showlegend=trace.get("showlegend", True),
        visible=trace.get("visible", True),
    )


def _passthrough(trace):
    return trace


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TRACE_SPECS: dict[TraceType, TraceTypeSpec] = {
    TraceType.POLYGON: TraceTypeSpec(
        name="polygon",
        layer_order=10,
        match=_match_polygon,
        reconstruct=_passthrough,
    ),
    TraceType.MOSAIC: TraceTypeSpec(
        name="mosaic",
        layer_order=20,
        match=_match_mosaic,
        reconstruct=_reconstruct_mosaic,
    ),
    TraceType.MASK_OVERLAY: TraceTypeSpec(
        name="mask_overlay",
        layer_order=30,
        match=_match_mask_overlay,
        reconstruct=_reconstruct_mask_overlay,
    ),
    TraceType.CATRED: TraceTypeSpec(
        name="catred",
        layer_order=40,
        match=_match_catred,
        reconstruct=_reconstruct_catred,
    ),
    TraceType.NED_SPECZ: TraceTypeSpec(
        name="ned_specz",
        layer_order=45,
        match=_match_ned_specz,
        reconstruct=_reconstruct_ned_specz,
    ),
    TraceType.MEMBERS: TraceTypeSpec(
        name="members",
        layer_order=50,
        match=_match_members,
        reconstruct=_reconstruct_members,
    ),
    TraceType.MATCHED_PAIR: TraceTypeSpec(
        name="matched_pair",
        layer_order=55,
        match=_match_matched_pair,
        reconstruct=_passthrough,
    ),
    TraceType.CLUSTER: TraceTypeSpec(
        name="cluster",
        layer_order=60,
        match=_match_cluster,
        reconstruct=_passthrough,
    ),
    TraceType.SELECTED_CLUSTER: TraceTypeSpec(
        name="selected_cluster",
        layer_order=70,
        match=_match_selected_cluster,
        reconstruct=_passthrough,
    ),
}

# Ordered list for classification — checked in this order, first match wins.
# Order matters: more specific types before broader ones.
_MATCH_ORDER = [
    TraceType.SELECTED_CLUSTER,
    TraceType.MATCHED_PAIR,
    TraceType.MEMBERS,
    TraceType.MASK_OVERLAY,
    TraceType.CATRED,
    TraceType.NED_SPECZ,
    TraceType.POLYGON,
    TraceType.MOSAIC,
    TraceType.CLUSTER,
]


class TraceRegistry:
    """Centralized trace extraction, classification, and reassembly."""

    @staticmethod
    def classify_trace(trace) -> Optional[TraceType]:
        """Determine the TraceType of a given trace (dict or Plotly object)."""
        name = _get_trace_name(trace)
        if not name:
            return None
        for trace_type in _MATCH_ORDER:
            if TRACE_SPECS[trace_type].match(trace):
                return trace_type
        return None

    @staticmethod
    def extract_traces(
        figure: dict,
        trace_types: set,
        reconstruct: bool = True,
    ) -> dict:
        """
        Extract traces of specified types from a figure.

        Returns dict mapping TraceType -> list of extracted traces.
        """
        result = {tt: [] for tt in trace_types}
        if not figure or "data" not in figure:
            return result

        for trace in figure["data"]:
            classified = TraceRegistry.classify_trace(trace)
            if classified in trace_types:
                spec = TRACE_SPECS[classified]
                if reconstruct and isinstance(trace, dict):
                    result[classified].append(spec.reconstruct(trace))
                else:
                    result[classified].append(trace)

        return result

    @staticmethod
    def extract_all_preserved(
        figure: dict,
        exclude: set = frozenset(),
    ) -> dict:
        """
        Extract ALL trace types from a figure except those in `exclude`.

        Callers specify what they are REPLACING; everything else is preserved.
        This prevents the "forgot to preserve X" bug.
        """
        preserve_types = set(TraceType) - exclude
        return TraceRegistry.extract_traces(figure, preserve_types)

    @staticmethod
    def categorize_all(figure: dict) -> dict:
        """
        Classify every trace in figure into its TraceType bucket.
        Unclassified traces go under None key.
        """
        result = {tt: [] for tt in TraceType}
        result[None] = []
        if not figure or "data" not in figure:
            return result

        for trace in figure["data"]:
            classified = TraceRegistry.classify_trace(trace)
            result[classified].append(trace)

        return result

    @staticmethod
    def assemble_in_layer_order(categorized_traces: dict) -> list:
        """
        Reassemble traces in correct layer order (bottom to top).
        Accepts dict with TraceType keys (None key placed at end before clusters).
        """
        ordered = []
        unclassified = categorized_traces.get(None, [])

        for trace_type in sorted(
            [k for k in categorized_traces.keys() if k is not None],
            key=lambda tt: TRACE_SPECS[tt].layer_order,
        ):
            traces = categorized_traces[trace_type]
            ordered.extend(traces)
            if trace_type == TraceType.CATRED and unclassified:
                ordered.extend(unclassified)

        if not any(tt for tt in categorized_traces if tt is not None and TRACE_SPECS[tt].layer_order >= 40):
            ordered.extend(unclassified)

        return ordered
