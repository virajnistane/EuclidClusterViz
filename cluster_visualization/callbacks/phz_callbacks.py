"""
PHZ (Photometric Redshift) callbacks for cluster visualization.

Handles PHZ_PDF plot updates when clicking on CATRED data points,
including redshift probability distribution visualization and related UI interactions.
"""

import dash  # type: ignore[import]
from dash import Input, Output
import plotly.graph_objs as go  # type: ignore[import]
import numpy as np


class PHZCallbacks:
    """Handles PHZ_PDF plot callbacks"""

    def __init__(self, app, catred_handler=None):
        """
        Initialize PHZ callbacks.

        Args:
            app: Dash application instance
            catred_handler: CATREDHandler instance for CATRED data operations (optional)
        """
        self.app = app
        self.catred_handler = catred_handler

        # Fallback attributes for backward compatibility
        self.current_catred_data = None

        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all PHZ-related callbacks"""
        self._setup_phz_pdf_callback()

    def _setup_phz_pdf_callback(self):
        """Setup callback for handling clicks on CATRED data points to show PHZ_PDF"""

        @self.app.callback(
            Output("phz-pdf-plot", "figure", allow_duplicate=True),
            [Input("cluster-plot", "clickData")],
            [
                dash.dependencies.State("cluster-plot", "figure")
            ],  # Add figure state to get trace names
            prevent_initial_call=True,
        )
        def update_phz_pdf_plot(clickData, current_figure):
            print("=== PHZ CALLBACK TRIGGERED ===")
            print(f"Debug: Click callback triggered with clickData: {clickData}")
            print(f"Debug: clickData type: {type(clickData)}")

            if not clickData:
                print("Debug: No clickData received")
                return dash.no_update

            # Get current CATRED data from handler or fallback
            current_catred_data = None
            data_source = "none"

            if (
                self.catred_handler
                and hasattr(self.catred_handler, "current_catred_data")
                and self.catred_handler.current_catred_data
            ):
                current_catred_data = self.catred_handler.current_catred_data
                data_source = "catred_handler"
                print("Debug: Using current_catred_data from catred_handler")
            elif (
                hasattr(self, "trace_creator")
                and self.trace_creator
                and hasattr(self.trace_creator, "current_catred_data")
                and self.trace_creator.current_catred_data
            ):
                current_catred_data = self.trace_creator.current_catred_data
                data_source = "trace_creator"
                print("Debug: Using current_catred_data from trace_creator")
            elif hasattr(self, "current_catred_data") and self.current_catred_data:
                current_catred_data = self.current_catred_data
                data_source = "self"
                print("Debug: Using current_catred_data from self")

            print(
                f"Debug: Data source: {data_source}, data available: {current_catred_data is not None}"
            )
            if current_catred_data:
                print(f"Debug: Data keys: {list(current_catred_data.keys())}")
                print(f"Debug: Data memory id: {id(current_catred_data)}")

            if not current_catred_data:
                print(f"Debug: No current_catred_data available from any source")
                print(f"Debug: catred_handler available: {self.catred_handler is not None}")
                print(
                    f"Debug: trace_creator available: {hasattr(self, 'trace_creator') and self.trace_creator is not None}"
                )
                print(
                    f"Debug: self.current_catred_data available: {hasattr(self, 'current_catred_data')}"
                )
                return dash.no_update

            try:
                # Extract click information
                clicked_point = clickData["points"][0]
                print(f"Debug: Clicked point: {clicked_point}")

                # Get the trace name using curveNumber (Scattergl doesn't provide traceName)
                curve_number = clicked_point.get("curveNumber", None)
                clicked_trace_name = "Unknown"

                # Retrieve trace name from figure state using curveNumber
                if current_figure and curve_number is not None:
                    try:
                        traces = current_figure.get("data", [])
                        if curve_number < len(traces):
                            clicked_trace_name = traces[curve_number].get("name", "Unknown")
                            print(
                                f"Debug: Retrieved trace name from figure using curveNumber {curve_number}: '{clicked_trace_name}'"
                            )
                    except Exception as e:
                        print(f"Warning: Could not retrieve trace name from figure: {e}")

                print(f"Debug: Clicked trace name: '{clicked_trace_name}'")

                # Get coordinates for matching
                clicked_x = clicked_point.get("x")
                clicked_y = clicked_point.get("y")
                print(f"Debug: Clicked coordinates: ({clicked_x}, {clicked_y})")

                # Get point index from pointNumber (more reliable than customdata)
                point_number = clicked_point.get("pointNumber", None)
                custom_data = clicked_point.get("customdata", None)
                print(f"Debug: Point number (index in trace): {point_number}")
                print(f"Debug: Custom data (may be coverage value, not index): {custom_data}")

                # Additional click data debugging
                print(f"Debug: All click data keys: {list(clicked_point.keys())}")
                if "curveNumber" in clicked_point:
                    print(f"Debug: Curve number: {clicked_point['curveNumber']}")

                # Search through stored CATRED data to find the matching trace
                found_catred_data = None
                point_index = None

                print(f"Debug: Available CATRED data traces: {list(current_catred_data.keys())}")
                print(f"Debug: Looking for traces containing 'CATRED'")

                # First, try to match the exact clicked trace name if it's a CATRED trace
                if (
                    clicked_trace_name != "Unknown"
                    and "CATRED" in clicked_trace_name
                    and clicked_trace_name in current_catred_data
                ):
                    catred_data = current_catred_data[clicked_trace_name]
                    print(
                        f"Debug: Direct match found for clicked trace '{clicked_trace_name}' with {len(catred_data['ra'])} points"
                    )

                    # Use pointNumber (most reliable - it's the index in the trace array)
                    if point_number is not None and point_number < len(catred_data["ra"]):
                        found_catred_data = catred_data
                        point_index = point_number
                        print(f"Debug: Using pointNumber as index: {point_index}")
                    # Fallback to coordinate matching if pointNumber not available
                    elif clicked_x is not None and clicked_y is not None:
                        print(
                            f"Debug: Attempting coordinate matching for ({clicked_x}, {clicked_y})"
                        )
                        for i, (x, y) in enumerate(zip(catred_data["ra"], catred_data["dec"])):
                            distance = ((x - clicked_x) ** 2 + (y - clicked_y) ** 2) ** 0.5
                            if distance < 1e-6:  # Tight tolerance for direct match
                                found_catred_data = catred_data
                                point_index = i
                                print(
                                    f"Debug: Found matching point by coordinates at index: {point_index}"
                                )
                                break

                # If direct match failed, search through all CATRED traces
                if not found_catred_data:
                    print(f"Debug: No direct match, searching all CATRED traces...")

                    for trace_name, catred_data in current_catred_data.items():
                        print(f"Debug: Checking trace: '{trace_name}'")

                        # Check if this is a CATRED trace (updated for new naming scheme)
                        if (
                            "CATRED" in trace_name
                        ):  # and ('Data' in trace_name or 'High-Res' in trace_name):
                            print(
                                f"Debug: Found CATRED trace '{trace_name}' with {len(catred_data['ra'])} points"
                            )

                            # Method 1: Use pointNumber if available (most reliable)
                            if point_number is not None and point_number < len(catred_data["ra"]):
                                found_catred_data = catred_data
                                point_index = point_number
                                print(f"Debug: Using pointNumber as index: {point_index}")
                                break

                            # Method 2: Match coordinates with relaxed tolerance (fallback)
                            elif clicked_x is not None and clicked_y is not None:
                                print(
                                    f"Debug: Attempting coordinate matching for ({clicked_x}, {clicked_y})"
                                )
                                best_match_index = None
                                best_distance = float("inf")

                                for i, (x, y) in enumerate(
                                    zip(catred_data["ra"], catred_data["dec"])
                                ):
                                    distance = ((x - clicked_x) ** 2 + (y - clicked_y) ** 2) ** 0.5
                                    if (
                                        distance < 0.001 and distance < best_distance
                                    ):  # Relaxed tolerance
                                        best_match_index = i
                                        best_distance = distance

                                if best_match_index is not None:
                                    found_catred_data = catred_data
                                    point_index = best_match_index
                                    print(
                                        f"Debug: Found matching point by coordinates at index: {point_index} (distance: {best_distance:.6f})"
                                    )
                                    break
                                else:
                                    print(
                                        f"Debug: No coordinate match found in trace '{trace_name}'"
                                    )
                        else:
                            print(f"Debug: Skipping non-CATRED trace: '{trace_name}'")

                # Additional debugging if no match found
                if not found_catred_data:
                    print("Debug: No CATRED trace matched the click")
                    print(f"Debug: Available trace names: {list(current_catred_data.keys())}")
                    print(f"Debug: Click data keys: {clicked_point.keys()}")
                    print(f"Debug: Full clicked point data: {clicked_point}")

                if found_catred_data and point_index is not None:
                    print(f"Debug: Successfully found CATRED data for point index: {point_index}")

                    # Get PHZ_PDF data for this point
                    phz_pdf = found_catred_data["phz_pdf"][point_index]
                    ra = found_catred_data["ra"][point_index]
                    dec = found_catred_data["dec"][point_index]
                    phz_mode_1 = found_catred_data["phz_mode_1"][point_index]
                    phz_median = found_catred_data["phz_median"][point_index]

                    print(
                        f"Debug: PHZ_PDF length: {len(phz_pdf)}, PHZ_MODE_1: {phz_mode_1}, PHZ_MEDIAN: {phz_median}"
                    )

                    return self._create_phz_pdf_plot(phz_pdf, ra, dec, phz_mode_1, phz_median)
                else:
                    print("Debug: Click was not on a CATRED data point")

                # If we get here, the click wasn't on a CATRED point
                return dash.no_update

            except Exception as e:
                print(f"Debug: Error creating PHZ_PDF plot: {e}")
                import traceback

                print(f"Debug: Traceback: {traceback.format_exc()}")

                return self._create_error_phz_plot(str(e))

    def _create_phz_pdf_plot(self, phz_pdf, ra, dec, phz_mode_1, phz_median):
        """Create PHZ_PDF plot for a given CATRED point"""
        try:
            # Validate PHZ_PDF data
            if not phz_pdf or len(phz_pdf) == 0:
                print(f"Debug: Empty PHZ_PDF data")
                return self._create_error_phz_plot("Empty PHZ_PDF data")

            # Convert to numpy array for safety
            phz_pdf_array = np.array(phz_pdf)

            # Check for NaN or infinite values
            if np.any(np.isnan(phz_pdf_array)) or np.any(np.isinf(phz_pdf_array)):
                print(f"Debug: PHZ_PDF contains NaN or infinite values")
                return self._create_error_phz_plot("PHZ_PDF contains invalid values")

            # Create redshift bins (assuming typical range for photometric redshift)
            z_bins = np.linspace(0, 3, len(phz_pdf_array))

            # Create PHZ_PDF plot
            phz_fig = go.Figure()

            phz_fig.add_trace(
                go.Scatter(
                    x=z_bins,
                    y=phz_pdf_array,
                    mode="lines+markers",
                    name="PHZ_PDF",
                    line=dict(color="blue", width=2),
                    marker=dict(size=4),
                    fill="tozeroy",  # Fill to zero y-axis instead of previous trace
                )
            )

            # Add vertical line for PHZ_MODE_1
            phz_fig.add_vline(
                x=phz_mode_1,
                line=dict(color="red", width=2, dash="dash"),
                annotation_text=f"PHZ_MODE_1: {phz_mode_1:.3f}",
                annotation_position="top",
            )

            phz_fig.add_vline(
                x=phz_median,
                line=dict(color="green", width=2, dash="dot"),
                annotation_text=f"PHZ_MEDIAN: {phz_median:.3f}",
                annotation_position="top left" if phz_median < phz_mode_1 else "top right",
            )

            phz_fig.update_layout(
                title=f"PHZ_PDF for CATRED Point at RA: {ra:.6f}, Dec: {dec:.6f}",
                xaxis_title="Redshift (z)",
                yaxis_title="Probability Density",
                margin=dict(l=40, r=20, t=60, b=40),
                showlegend=True,
                hovermode="x unified",
            )

            print(f"Debug: Created PHZ_PDF plot for point at RA: {ra:.6f}, Dec: {dec:.6f}")
            return phz_fig

        except Exception as e:
            print(f"Debug: Error in _create_phz_pdf_plot: {e}")
            import traceback

            print(f"Debug: Traceback: {traceback.format_exc()}")
            return self._create_error_phz_plot(f"Error creating plot: {str(e)}")

    def _create_error_phz_plot(self, error_message):
        """Create error PHZ_PDF plot"""
        error_fig = go.Figure()
        error_fig.update_layout(
            title="PHZ_PDF Plot - Error",
            xaxis_title="Redshift",
            yaxis_title="Probability Density",
            margin=dict(l=40, r=20, t=40, b=40),
            showlegend=False,
            annotations=[
                dict(
                    text=f"Error loading PHZ_PDF data: {error_message}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    xanchor="center",
                    yanchor="middle",
                    showarrow=False,
                    font=dict(size=12, color="red"),
                )
            ],
        )
        return error_fig
