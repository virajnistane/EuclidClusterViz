"""
NED spec-z verification catalog callbacks for cluster visualization.

Handles showing/hiding the Mask-card NED spec-z section (tied to the
cluster spec-z filter switch) and rendering the NED galaxy markers, styled
distinctly from CATRED, for manual verification against CATRED sources.
"""

import plotly.graph_objs as go
from dash import Input, Output, State

from cluster_visualization.src.data.ned_catred_matcher import match_ned_to_catred
from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType


class NEDCallbacks:
    """Handles NED spec-z verification catalog display callbacks"""

    def __init__(self, app, ned_handler, figure_manager=None, catred_handler=None, data_loader=None):
        """
        Initialize NED spec-z callbacks.

        Args:
            app: Dash application instance
            ned_handler: NEDHandler instance for the spec-z catalog
            figure_manager: FigureManager instance (unused here, kept for
                constructor-injection consistency with other callback classes)
            catred_handler: CATREDHandler instance, used to auto-load CATRED
                tiles around the plotted NED galaxies for the nearby-CATRED
                display option
            data_loader: DataLoader instance, used to fetch the main MER
                tile/catred_info data dict the CATRED handler needs
        """
        self.app = app
        self.ned_handler = ned_handler
        self.figure_manager = figure_manager
        self.catred_handler = catred_handler
        self.data_loader = data_loader

        self._setup_section_visibility_callback()
        self._setup_display_callback()
        self._setup_nearby_section_visibility_callback()
        self._setup_nearby_catred_button_state_callback()
        self._setup_nearby_catred_callback()

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

    def _setup_nearby_section_visibility_callback(self):
        """Show the nearby-CATRED option only once NED galaxies are displayed."""

        @self.app.callback(
            Output("ned-nearby-catred-wrapper", "style"),
            Input("ned-specz-display-switch", "value"),
        )
        def toggle_nearby_catred_section(show_galaxies):
            return {"display": "block"} if show_galaxies else {"display": "none"}

    def _setup_nearby_catred_button_state_callback(self):
        """Clientside callback: enable/disable the nearby-CATRED button based on zoom level.

        Mirrors CATREDCallbacks._setup_catred_button_state_callback exactly -
        same <2 deg x <2 deg RA/Dec-span gate, same figure.layout range
        fallback, same "no main data loaded yet" gate via render-button's
        n_clicks - so nearby-CATRED loading never fires on a whole-survey
        viewport.
        """
        self.app.clientside_callback(
            """
            function(relayoutData, nClicks, figure) {
                if (!nClicks || nClicks === 0) return true;

                var raRange = null, decRange = null;

                if (relayoutData) {
                    if ('xaxis.range[0]' in relayoutData && 'xaxis.range[1]' in relayoutData) {
                        raRange = Math.abs(relayoutData['xaxis.range[1]'] - relayoutData['xaxis.range[0]']);
                    } else if (relayoutData['xaxis.range']) {
                        raRange = Math.abs(relayoutData['xaxis.range'][1] - relayoutData['xaxis.range'][0]);
                    }
                    if ('yaxis.range[0]' in relayoutData && 'yaxis.range[1]' in relayoutData) {
                        decRange = Math.abs(relayoutData['yaxis.range[1]'] - relayoutData['yaxis.range[0]']);
                    } else if (relayoutData['yaxis.range']) {
                        decRange = Math.abs(relayoutData['yaxis.range'][1] - relayoutData['yaxis.range'][0]);
                    }
                }

                if ((raRange === null || decRange === null) && figure && figure.layout) {
                    var layout = figure.layout;
                    if (layout.xaxis && layout.xaxis.range && layout.xaxis.range.length === 2) {
                        raRange = Math.abs(layout.xaxis.range[1] - layout.xaxis.range[0]);
                    }
                    if (layout.yaxis && layout.yaxis.range && layout.yaxis.range.length === 2) {
                        decRange = Math.abs(layout.yaxis.range[1] - layout.yaxis.range[0]);
                    }
                }

                if (raRange !== null && decRange !== null && raRange < 2.0 && decRange < 2.0) {
                    return false;
                }
                return true;
            }
            """,
            Output("ned-nearby-catred-button", "disabled"),
            Input("cluster-plot", "relayoutData"),
            [State("render-button", "n_clicks"), State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )

    def _setup_nearby_catred_callback(self):
        """Add the CATRED-near-NED marker trace when the button is clicked.

        Manual, button-triggered (not a live switch) so the viewport is only
        matched against on demand, and the button itself is disabled unless
        zoomed in - never loads CATRED for the whole NED catalog's footprint.
        """

        @self.app.callback(
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("ned-nearby-catred-button", "n_clicks"),
            State("ned-nearby-catred-radius-arcsec", "value"),
            State("algorithm-dropdown", "value"),
            State("catred-mode-switch", "value"),
            State("catred-threshold-slider", "value"),
            State("magnitude-limit-slider", "value"),
            State("cluster-plot", "relayoutData"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )
        def load_nearby_catred(
            n_clicks, radius_arcsec, algorithm, catred_masked, threshold, maglim, relayout_data, current_figure
        ):
            if not n_clicks or not current_figure or "data" not in current_figure:
                return current_figure

            categorized = TraceRegistry.extract_all_preserved(
                current_figure, exclude={TraceType.NED_NEARBY_CATRED}
            )

            nearby_traces = []
            if (
                self.ned_handler is not None
                and self.ned_handler.is_available()
                and self.catred_handler is not None
                and self.data_loader is not None
            ):
                try:
                    nearby_traces = self._find_nearby_catred_traces(
                        radius_arcsec, algorithm, catred_masked, threshold, maglim,
                        relayout_data, current_figure,
                    )
                except Exception as e:
                    print(f"Error finding CATRED sources near NED galaxies: {e}")

            categorized[TraceType.NED_NEARBY_CATRED] = nearby_traces
            current_figure["data"] = TraceRegistry.assemble_in_layer_order(categorized)
            return current_figure

    @staticmethod
    def _parse_axis_range(relayout_data, axis_prefix):
        """Parse a Plotly axis range out of relayoutData, accepting both the
        indexed form ("xaxis.range[0]"/"[1]") and the list form
        ("xaxis.range": [min, max]) - Plotly emits either depending on the
        interaction (box-zoom drag vs. programmatic/Aladin-synced relayout).
        This mirrors the parsing already used by the clientside zoom-gate
        (_setup_nearby_catred_button_state_callback) so the button's enabled
        state and this extraction always agree on what counts as "zoomed"."""
        if not relayout_data:
            return None
        key0, key1, key_list = f"{axis_prefix}.range[0]", f"{axis_prefix}.range[1]", f"{axis_prefix}.range"
        if key0 in relayout_data and key1 in relayout_data:
            return relayout_data[key0], relayout_data[key1]
        if key_list in relayout_data and len(relayout_data[key_list]) == 2:
            return relayout_data[key_list][0], relayout_data[key_list][1]
        return None

    def _get_current_viewport(self, relayout_data, current_figure):
        """Get the current RA/Dec viewport, falling back to the figure's own
        axis ranges when no relayout event has fired yet (mirrors the
        clientside zoom-gate's JS fallback)."""
        ra_range = self._parse_axis_range(relayout_data, "xaxis")
        dec_range = self._parse_axis_range(relayout_data, "yaxis")

        if ra_range is None or dec_range is None:
            layout = (current_figure or {}).get("layout", {}) or {}
            xaxis_range = (layout.get("xaxis") or {}).get("range")
            yaxis_range = (layout.get("yaxis") or {}).get("range")
            if ra_range is None and xaxis_range and len(xaxis_range) == 2:
                ra_range = (xaxis_range[0], xaxis_range[1])
            if dec_range is None and yaxis_range and len(yaxis_range) == 2:
                dec_range = (yaxis_range[0], yaxis_range[1])

        if ra_range is None or dec_range is None:
            return None

        ra_min, ra_max = sorted(ra_range)
        dec_min, dec_max = sorted(dec_range)
        return {"ra_min": ra_min, "ra_max": ra_max, "dec_min": dec_min, "dec_max": dec_max}

    def _find_nearby_catred_traces(
        self, radius_arcsec, algorithm, catred_masked, threshold, maglim, relayout_data, current_figure
    ):
        """Auto-load CATRED tiles covering only the NED galaxies currently in
        view, and return matched traces. Never loads CATRED for the whole
        NED catalog's footprint - if there is no zoomed-in viewport, or no
        NED galaxies are in it, no CATRED tile load happens at all."""
        df = self.ned_handler.get_all_galaxies()
        if df is None or len(df) == 0 or "RA" not in df.columns or "DEC" not in df.columns:
            return []

        radius_deg = max(float(radius_arcsec or 0.0), 0.0) / 3600.0
        if radius_deg <= 0:
            return []

        viewport = self._get_current_viewport(relayout_data, current_figure)
        if viewport is None:
            print("Debug: No zoomed-in viewport available for NED-nearby-CATRED matching")
            return []

        all_ned_ra = df["RA"].to_numpy()
        all_ned_dec = df["DEC"].to_numpy()

        in_view = (
            (all_ned_ra >= viewport["ra_min"])
            & (all_ned_ra <= viewport["ra_max"])
            & (all_ned_dec >= viewport["dec_min"])
            & (all_ned_dec <= viewport["dec_max"])
        )
        df_in_view = df[in_view].reset_index(drop=True)
        ned_ra = df_in_view["RA"].to_numpy()
        ned_dec = df_in_view["DEC"].to_numpy()
        print(f"Debug: NED-nearby-CATRED: {len(ned_ra)} NED galaxies in current viewport")
        if len(ned_ra) == 0:
            return []

        data = self.data_loader.load_data(algorithm)
        result = match_ned_to_catred(
            df_in_view, self.catred_handler, data, radius_arcsec, catred_masked, threshold, maglim
        )
        if result is None:
            print("Debug: NED-nearby-CATRED: no CATRED points loaded for this viewport")
            return []

        if len(result.nearest_rows) > 0:
            print(
                f"Debug: NED-nearby-CATRED: recording {len(result.nearest_rows)} "
                "nearest-match row(s) to output file"
            )
            try:
                self.ned_handler.write_catred_matches(result.nearest_rows)
            except Exception as e:
                print(f"Warning: Failed to record NED-nearby-CATRED matches: {e}")

        if len(result.display_matched_idx) == 0:
            print(
                f"Debug: NED-nearby-CATRED: 0 of {len(result.catred_ra)} CATRED sources within "
                f"{radius_arcsec} arcsec of any of {len(ned_ra)} NED galaxies in view "
                f"(nearest CATRED source is {result.overall_nearest_arcsec:.2f} arcsec away - "
                "try a larger radius)"
            )
            return []

        idx = result.display_matched_idx
        print(f"Debug: NED-nearby-CATRED: matched {len(idx)} CATRED sources within {radius_arcsec} arcsec")

        hover_text = self._format_catred_hover_text(result.catred_scatter, idx)
        return [self._build_nearby_catred_trace(result.catred_ra[idx], result.catred_dec[idx], hover_text)]

    @staticmethod
    def _format_catred_hover_text(catred_scatter, idx):
        """Format hover text for the matched subset, identical to
        TraceCreator._format_catred_hover_text (traces.py:792) so these
        markers carry the same information as the regular CATRED trace."""
        phz_median = catred_scatter.get("phz_median", [])
        phz_mode_1 = catred_scatter.get("phz_mode_1", [])
        phz_70_int = catred_scatter.get("phz_70_int", [])
        effective_coverage = catred_scatter.get("effective_coverage", [])

        hover_texts = []
        for i in idx:
            x = catred_scatter["ra"][i]
            y = catred_scatter["dec"][i]
            text = f"CATRED Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}"
            if i < len(phz_mode_1):
                text += f"<br>PHZ_MODE_1: {phz_mode_1[i]:.3f}"
            if i < len(phz_median):
                text += f"<br>PHZ_MEDIAN: {phz_median[i]:.3f}"
            if i < len(phz_70_int):
                p70 = phz_70_int[i]
                text += f"<br>PHZ_70_INT: {abs(float(p70[1]) - float(p70[0])):.3f}"
            if i < len(effective_coverage):
                text += f"<br>Effective Coverage: {effective_coverage[i]:.3f}"
            hover_texts.append(text)

        return hover_texts

    @staticmethod
    def _build_nearby_catred_trace(ra, dec, text):
        """Build the CATRED-near-NED marker trace, styled distinctly from both
        the NED diamond markers and the transparent CATRED overlay markers."""
        return go.Scattergl(
            x=ra,
            y=dec,
            mode="markers",
            marker=dict(
                size=9,
                symbol="square",
                color="rgba(0, 150, 255, 0)",
                line=dict(width=1.5, color="darkblue"),
            ),
            name="NED-Nearby CATRED Sources",
            hoverinfo="text",
            text=text,
            showlegend=True,
        )

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
