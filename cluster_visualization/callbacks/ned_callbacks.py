"""
NED spec-z verification catalog callbacks for cluster visualization.

Handles showing/hiding the Mask-card NED spec-z section (tied to the
cluster spec-z filter switch) and rendering the NED galaxy markers, styled
distinctly from CATRED, for manual verification against CATRED sources.
"""

import plotly.graph_objs as go
from dash import Input, Output, State

from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType


class NEDCallbacks:
    """Handles NED spec-z verification catalog display callbacks"""

    def __init__(self, app, ned_handler, figure_manager=None):
        """
        Initialize NED spec-z callbacks.

        Args:
            app: Dash application instance
            ned_handler: NEDHandler instance for the spec-z catalog
            figure_manager: FigureManager instance (unused here, kept for
                constructor-injection consistency with other callback classes)
        """
        self.app = app
        self.ned_handler = ned_handler
        self.figure_manager = figure_manager

        self._setup_section_visibility_callback()
        self._setup_display_callback()

    def _setup_section_visibility_callback(self):
        """Show the Mask-card NED section only when the cluster filter switch is active."""

        @self.app.callback(
            Output("ned-specz-section-wrapper", "style"),
            Input("ned-specz-filter-switch", "value"),
        )
        def toggle_ned_specz_section(filter_active):
            return {"display": "block"} if filter_active else {"display": "none"}

    def _setup_display_callback(self):
        """Add/remove the NED galaxy marker trace based on the display switch."""

        @self.app.callback(
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("ned-specz-display-switch", "value"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )
        def toggle_ned_specz_display(show_galaxies, current_figure):
            if not current_figure or "data" not in current_figure:
                return current_figure

            categorized = TraceRegistry.extract_all_preserved(
                current_figure, exclude={TraceType.NED_SPECZ}
            )

            ned_traces = []
            if show_galaxies and self.ned_handler is not None and self.ned_handler.is_available():
                df = self.ned_handler.get_all_galaxies()
                if df is not None and len(df) > 0:
                    ned_traces = [self._build_ned_trace(df)]

            categorized[TraceType.NED_SPECZ] = ned_traces
            current_figure["data"] = TraceRegistry.assemble_in_layer_order(categorized)
            return current_figure

    @staticmethod
    def _build_ned_trace(df):
        """Build the NED spec-z galaxy Scattergl trace, styled distinctly from CATRED."""
        z = df["Z"] if "Z" in df.columns else None
        zflag = df["ZFLAG"] if "ZFLAG" in df.columns else None
        zref = df["ZREF"] if "ZREF" in df.columns else None
        r_mpc = df["R_MPC"] if "R_MPC" in df.columns else None

        text = [
            f"Z={z.iloc[i]:.4f}<br>ZFLAG={zflag.iloc[i]}<br>ZREF={zref.iloc[i]}<br>R_MPC={r_mpc.iloc[i]:.3f}"
            if z is not None and zflag is not None and zref is not None and r_mpc is not None
            else ""
            for i in range(len(df))
        ]

        return go.Scattergl(
            x=df["RA"],
            y=df["DEC"],
            mode="markers",
            marker=dict(
                size=7,
                symbol="diamond",
                color="#ff8800",
                line=dict(width=1, color="black"),
            ),
            name="NED Spec-z Galaxies",
            text=text,
            hoverinfo="text",
            showlegend=True,
        )
