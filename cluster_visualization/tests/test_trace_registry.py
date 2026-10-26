"""Tests for the centralized trace registry module."""

import pytest
from cluster_visualization.src.visualization.trace_registry import (
    TraceRegistry,
    TraceType,
    TRACE_SPECS,
    _get_trace_name,
)


# ---------------------------------------------------------------------------
# Sample trace dicts
# ---------------------------------------------------------------------------

SAMPLE_TRACES = {
    "catred_masked": {"name": "CATRED Masked - MER Tile", "type": "scattergl", "x": [1], "y": [2]},
    "catred_unmasked": {"name": "CATRED Unmasked - Boxed", "type": "scattergl", "x": [3], "y": [4]},
    "mosaic_image": {"name": "Mosaic (CDS) 12345", "type": "image", "source": "data:image/png;base64,..."},
    "mosaic_heatmap": {"name": "MER-Mosaic cutout #1", "type": "heatmap", "z": [[1, 2], [3, 4]]},
    "mosaic_placeholder": {"name": "Mosaic 12345 (Placeholder)", "type": "heatmap", "z": [[0]]},
    "mask_overlay_bin": {"name": "Mask overlay bin 3", "type": "scatter", "x": [1], "y": [2]},
    "inverted_mask": {"name": "Inverted mask overlay", "type": "scatter", "x": [], "y": []},
    "mask_colorbar": {"name": "Mask Colorbar", "type": "scatter", "marker": {"colorscale": "viridis"}},
    "mask_aladin": {"name": "Mask aladin moc", "type": "scatter", "customdata": [1, 2, 3]},
    "inverted_mask_aladin": {"name": "Inverted mask aladin moc", "type": "scatter"},
    "polygon_lev1": {"name": "Tile 100 LEV1", "type": "scatter", "x": [1], "y": [2]},
    "polygon_core": {"name": "Tile 100 CORE", "type": "scatter", "x": [3], "y": [4]},
    "polygon_mertile": {"name": "MER-Tile 200", "type": "scatter", "x": [5], "y": [6]},
    "members": {"name": "Members (ID 42)", "type": "scattergl", "x": [7], "y": [8]},
    "matched_pair": {"name": "Matched Pair", "type": "scatter", "x": [9], "y": [10]},
    "selected": {"name": "__selected_cluster__", "type": "scattergl", "x": [11], "y": [12]},
    "merged_pzwav": {"name": "Merged PZWAV", "type": "scattergl", "x": [13], "y": [14]},
    "merged_amico": {"name": "Merged AMICO", "type": "scattergl", "x": [15], "y": [16]},
    "unmerged_tile": {"name": "PZWAV Unmerged-Tile 100", "type": "scattergl"},
    "enhanced": {"name": "PZWAV (Enhanced)", "type": "scattergl"},
    "proximity": {"name": "Cluster in Proximity", "type": "scattergl"},
    "unnamed": {"type": "scatter", "x": [0], "y": [0]},
}


# ---------------------------------------------------------------------------
# Test match predicates
# ---------------------------------------------------------------------------

class TestClassification:
    def test_catred_traces(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["catred_masked"]) == TraceType.CATRED
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["catred_unmasked"]) == TraceType.CATRED

    def test_mosaic_traces(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["mosaic_image"]) == TraceType.MOSAIC
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["mosaic_heatmap"]) == TraceType.MOSAIC
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["mosaic_placeholder"]) == TraceType.MOSAIC

    def test_mask_overlay_traces(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["mask_overlay_bin"]) == TraceType.MASK_OVERLAY
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["inverted_mask"]) == TraceType.MASK_OVERLAY
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["mask_colorbar"]) == TraceType.MASK_OVERLAY
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["mask_aladin"]) == TraceType.MASK_OVERLAY
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["inverted_mask_aladin"]) == TraceType.MASK_OVERLAY

    def test_polygon_traces(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["polygon_lev1"]) == TraceType.POLYGON
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["polygon_core"]) == TraceType.POLYGON
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["polygon_mertile"]) == TraceType.POLYGON

    def test_members_traces(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["members"]) == TraceType.MEMBERS

    def test_matched_pair(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["matched_pair"]) == TraceType.MATCHED_PAIR

    def test_selected_cluster(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["selected"]) == TraceType.SELECTED_CLUSTER

    def test_cluster_traces(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["merged_pzwav"]) == TraceType.CLUSTER
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["merged_amico"]) == TraceType.CLUSTER
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["unmerged_tile"]) == TraceType.CLUSTER
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["enhanced"]) == TraceType.CLUSTER
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["proximity"]) == TraceType.CLUSTER

    def test_unnamed_trace_returns_none(self):
        assert TraceRegistry.classify_trace(SAMPLE_TRACES["unnamed"]) is None

    def test_empty_name_returns_none(self):
        assert TraceRegistry.classify_trace({"name": "", "type": "scatter"}) is None


# ---------------------------------------------------------------------------
# Test extract_traces
# ---------------------------------------------------------------------------

class TestExtractTraces:
    def _make_figure(self, trace_keys):
        return {"data": [SAMPLE_TRACES[k] for k in trace_keys]}

    def test_extract_catred_only(self):
        fig = self._make_figure(["catred_masked", "mosaic_image", "merged_pzwav"])
        result = TraceRegistry.extract_traces(fig, {TraceType.CATRED})
        assert len(result[TraceType.CATRED]) == 1

    def test_extract_multiple_types(self):
        fig = self._make_figure([
            "catred_masked", "mosaic_image", "mask_colorbar", "merged_pzwav"
        ])
        result = TraceRegistry.extract_traces(
            fig, {TraceType.CATRED, TraceType.MOSAIC, TraceType.MASK_OVERLAY}
        )
        assert len(result[TraceType.CATRED]) == 1
        assert len(result[TraceType.MOSAIC]) == 1
        assert len(result[TraceType.MASK_OVERLAY]) == 1

    def test_extract_empty_figure(self):
        result = TraceRegistry.extract_traces(None, {TraceType.CATRED})
        assert result[TraceType.CATRED] == []

    def test_extract_no_matching(self):
        fig = self._make_figure(["merged_pzwav"])
        result = TraceRegistry.extract_traces(fig, {TraceType.CATRED})
        assert result[TraceType.CATRED] == []


# ---------------------------------------------------------------------------
# Test extract_all_preserved
# ---------------------------------------------------------------------------

class TestExtractAllPreserved:
    def test_excludes_specified_types(self):
        fig = {"data": [
            SAMPLE_TRACES["catred_masked"],
            SAMPLE_TRACES["mosaic_image"],
            SAMPLE_TRACES["merged_pzwav"],
            SAMPLE_TRACES["polygon_lev1"],
        ]}
        result = TraceRegistry.extract_all_preserved(
            fig, exclude={TraceType.CATRED, TraceType.CLUSTER}
        )
        assert TraceType.CATRED not in result or len(result.get(TraceType.CATRED, [])) == 0
        assert TraceType.CLUSTER not in result or len(result.get(TraceType.CLUSTER, [])) == 0
        assert len(result[TraceType.MOSAIC]) == 1
        assert len(result[TraceType.POLYGON]) == 1


# ---------------------------------------------------------------------------
# Test assemble_in_layer_order
# ---------------------------------------------------------------------------

class TestAssembleInLayerOrder:
    def test_correct_ordering(self):
        categorized = {
            TraceType.CLUSTER: [SAMPLE_TRACES["merged_pzwav"]],
            TraceType.CATRED: [SAMPLE_TRACES["catred_masked"]],
            TraceType.POLYGON: [SAMPLE_TRACES["polygon_lev1"]],
            TraceType.MOSAIC: [SAMPLE_TRACES["mosaic_image"]],
            TraceType.MASK_OVERLAY: [SAMPLE_TRACES["mask_colorbar"]],
        }
        ordered = TraceRegistry.assemble_in_layer_order(categorized)

        names = [t.get("name", "") if isinstance(t, dict) else t.name for t in ordered]
        polygon_idx = names.index("Tile 100 LEV1")
        mosaic_idx = names.index("Mosaic (CDS) 12345")
        mask_idx = names.index("Mask Colorbar")
        catred_idx = names.index("CATRED Masked - MER Tile")
        cluster_idx = names.index("Merged PZWAV")

        assert polygon_idx < mosaic_idx < mask_idx < catred_idx < cluster_idx

    def test_empty_categories(self):
        categorized = {TraceType.POLYGON: [], TraceType.CLUSTER: [SAMPLE_TRACES["merged_pzwav"]]}
        ordered = TraceRegistry.assemble_in_layer_order(categorized)
        assert len(ordered) == 1


# ---------------------------------------------------------------------------
# Regression: mask bug
# ---------------------------------------------------------------------------

class TestMaskOverlayBugRegression:
    """Ensure 'Mask Colorbar' and 'Inverted mask overlay' are classified as MASK_OVERLAY."""

    def test_mask_colorbar_classified(self):
        assert TraceRegistry.classify_trace({"name": "Mask Colorbar"}) == TraceType.MASK_OVERLAY

    def test_inverted_mask_classified(self):
        assert TraceRegistry.classify_trace({"name": "Inverted mask overlay"}) == TraceType.MASK_OVERLAY

    def test_inverted_mask_aladin_classified(self):
        assert TraceRegistry.classify_trace({"name": "Inverted mask aladin moc"}) == TraceType.MASK_OVERLAY


# ---------------------------------------------------------------------------
# Figures the browser sends back with Plotly typed arrays
# ---------------------------------------------------------------------------


class TestTypedArrays:
    """Plotly 6 serializes numpy data as {"dtype", "bdata"} when Dash sends a go.Figure; the
    figure comes back that way, and preserved traces must carry plain arrays again."""

    @staticmethod
    def _round_trip(traces):
        import json

        import plotly.graph_objs as go
        from plotly.io.json import to_json_plotly

        return json.loads(to_json_plotly(go.Figure(data=traces)))

    def test_catalog_and_link_traces_decode_for_the_dec_centre(self):
        import numpy as np
        import plotly.graph_objs as go

        from cluster_visualization.src.visualization.figures import FigureManager

        catalog = go.Scattergl(
            x=np.array([54.0, 54.2]),
            y=np.array([-51.0, -50.0]),
            customdata=np.array([3, 7]),
            name="Catalog: SPT",
            meta={"kind": "catalog"},
        )
        links = go.Scattergl(
            x=np.array([54.0, 54.01, np.nan]),
            y=np.array([-51.0, -50.99, np.nan]),
            mode="lines",
            name="Catalog match: SPT ↔ Euclid PZWAV (links)",
            meta={"kind": "catalog_match"},
        )
        figure = self._round_trip([catalog, links])
        assert isinstance(figure["data"][0]["y"], dict)  # typed array, as in the browser

        kinds = {TraceType.GALAXY_CATALOG, TraceType.CATALOG_MATCH}
        found = TraceRegistry.extract_traces(figure, kinds)
        (cat,) = found[TraceType.GALAXY_CATALOG]
        assert list(cat.y) == [-51.0, -50.0]
        assert list(cat.customdata) == [3, 7]
        traces = found[TraceType.GALAXY_CATALOG] + found[TraceType.CATALOG_MATCH]
        assert FigureManager()._extract_dec_center(traces) == pytest.approx(-50.995)
        # Raw dicts too (callers that skip reconstruction)
        assert FigureManager()._extract_dec_center(figure["data"]) == pytest.approx(-50.995)
        FigureManager().create_figure(traces, "PZWAV", False)  # the CATRED box path

    def test_decode_keeps_shape_and_other_values(self):
        import base64

        import numpy as np

        from cluster_visualization.src.visualization.trace_registry import decode_typed_array

        z = np.arange(6, dtype="f4").reshape(2, 3)
        typed = {"dtype": "f4", "bdata": base64.b64encode(z.tobytes()).decode(), "shape": "2, 3"}
        assert decode_typed_array(typed).tolist() == z.tolist()
        assert decode_typed_array([1, 2]) == [1, 2]
        assert decode_typed_array({"other": 1}) == {"other": 1}
