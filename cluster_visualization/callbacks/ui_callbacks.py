"""
UI callbacks for cluster visualization
"""

import os
from pathlib import Path
import glob
from dash import Input, Output, State, html, dash, ALL, callback_context
import dash_bootstrap_components as dbc
import base64
import csv
import io

try:
    from cluster_visualization.callbacks.utils import get_idclusters_array
except ImportError:
    print("Warning: Could not import get_idclusters_array from utils. ID cluster upload functionality may be affected.")

class UICallbacks:
    """Handles UI-related callbacks"""

    DEFAULT_CLTILE_INFO_HELP_TEXT = "Color clusters by tile; show MER tile polygons"
    DEFAULT_UNMERGED_HELP_TEXT = "Clusters in individual tiles but absent from merged catalog"
    NO_INDIVIDUAL_CLTILE_DATA_MESSAGE = "No individual CL-tile data available"

    # Range slider id -> id of its selected-range readout
    RANGE_SLIDER_READOUTS = {
        "snr-range-slider-pzwav": "snr-range-display-pzwav",
        "snr-range-slider-amico": "snr-range-display-amico",
        "redshift-range-slider": "redshift-range-display",
        "richness-range-slider-zp": "richness-range-display-zp",
        "richness-range-slider-rs": "richness-range-display-rs",
    }
    # Every button that triggers the main render (which reads all filter states)
    RENDER_TRIGGER_BUTTONS = ["render-button", "apply-filters-button"]
    # Filter states compared against the last render, grouped by the filter they belong to
    FILTER_STATE_GROUPS = {
        "Redshift": ["redshift-range-slider", "redshift-include-missing"],
        "SNR": [
            "snr-range-slider-pzwav",
            "snr-include-missing-pzwav",
            "snr-range-slider-amico",
            "snr-include-missing-amico",
        ],
        "Richness": [
            "richness-mode-radio",
            "richness-range-slider-zp",
            "richness-include-missing-zp",
            "flag-quality-zp-checklist",
            "richness-range-slider-rs",
            "richness-include-missing-rs",
            "flag-quality-rs-checklist",
        ],
        "Matched clusters": ["matching-clusters-switch"],
    }
    # Sidebar section id prefix -> starts open
    SIDEBAR_SECTIONS = {
        "clusters-settings": True,
        "filters-settings": True,
        "mask-controls": False,
        "image-controls": False,
        "display-options": False,
        "app-config": False,
    }

    def __init__(self, app, config=None, data_loader=None):
        """
        Initialize UI callbacks.

        Args:
            app: Dash application instance
            config: Configuration object (optional)
            data_loader: DataLoader instance (optional)
        """
        self.app = app
        self.config = config
        self.data_loader = data_loader
        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all UI-related callbacks"""
        self._setup_button_text_callbacks()
        self._setup_button_state_callbacks()
        self._setup_range_readout_callbacks()
        self._setup_catred_visibility_callback()
        self._setup_catred_render_color_callback()
        self._setup_catred_box_color_callback()
        self._setup_collapsible_callbacks()
        self._setup_config_display_callback()
        self._setup_file_configuration_callback()
        self._setup_file_browser_callbacks()
        self._setup_view_mode_callbacks()
        self._setup_status_toast_dismiss_callback()
        self._setup_getting_started_callback()
        self._setup_tutorial_tour_callback()

    def _setup_range_readout_callbacks(self):
        """Selected-range readouts, number inputs and "not applied" state for range sliders"""
        sliders = list(self.RANGE_SLIDER_READOUTS)

        state_ids = [i for ids in self.FILTER_STATE_GROUPS.values() for i in ids]
        # Snapshot every filter state (and the ID list) each time a render runs
        self.app.clientside_callback(
            """
            function() {
                const ids = %s;
                // Arguments: button n_clicks, then filter values, then upload contents + filename
                const args = Array.from(arguments);
                const n = ids.length;
                const values = args.slice(args.length - n - 2, args.length - 2);
                const applied = {};
                ids.forEach((id, i) => { applied[id] = values[i]; });
                const contents = args[args.length - 2];
                const filename = args[args.length - 1];
                applied['idcluster-upload'] = contents ? filename + ':' + contents.length : null;
                return applied;
            }
            """
            % state_ids,
            Output("applied-filters-store", "data"),
            [Input(button_id, "n_clicks") for button_id in self.RENDER_TRIGGER_BUTTONS],
            [State(i, "value") for i in state_ids]
            + [State("idcluster-upload", "contents"), State("idcluster-upload", "filename")],
            prevent_initial_call=True,
        )

        # Apply bar: which filters differ from the last render
        self.app.clientside_callback(
            """
            function() {
                const groups = %s;
                const args = Array.from(arguments);
                const applied = args[args.length - 1];
                const filename = args[args.length - 2];
                const contents = args[args.length - 3];
                if (!applied) {
                    return [true, 'secondary', true, 'Render once to enable filters'];
                }
                const current = {};
                let k = 0;
                Object.values(groups).forEach(ids => ids.forEach(id => { current[id] = args[k++]; }));
                current['idcluster-upload'] = contents ? filename + ':' + contents.length : null;
                // Checklist order follows click order, so compare arrays sorted
                const norm = v => Array.isArray(v) ? [...v].sort((x, y) => x - y) : v;
                const same = (a, b) => JSON.stringify(norm(a)) === JSON.stringify(norm(b));
                const changed = Object.keys(groups).filter(
                    name => groups[name].some(id => !same(current[id], applied[id]))
                );
                if (!same(current['idcluster-upload'], applied['idcluster-upload'])) {
                    changed.push('Cluster-ID list');
                }
                if (!changed.length) {
                    return [true, 'secondary', true, 'Plot matches these filters'];
                }
                return [false, 'primary', false, 'Changed: ' + changed.join(', ')];
            }
            """
            % self.FILTER_STATE_GROUPS,
            [
                Output("apply-filters-button", "disabled"),
                Output("apply-filters-button", "color"),
                Output("apply-filters-button", "outline"),
                Output("apply-filters-status", "children"),
            ],
            [Input(i, "value") for i in state_ids]
            + [
                Input("idcluster-upload", "contents"),
                Input("idcluster-upload", "filename"),
                Input("applied-filters-store", "data"),
            ],
        )

        # "Not applied" tag next to each non-slider filter control (sliders use their readout)
        tagged = [i for i in state_ids if i not in self.RANGE_SLIDER_READOUTS]
        self.app.clientside_callback(
            """
            function() {
                const ids = %s;
                const args = Array.from(arguments);
                const applied = args[args.length - 1];
                const filename = args[args.length - 2];
                const contents = args[args.length - 3];
                const hide = {display: 'none'}, show = {display: 'inline-block'};
                const keys = ids.concat(['idcluster-upload']);
                if (!applied) { return keys.map(() => hide); }
                const current = {};
                ids.forEach((id, i) => { current[id] = args[i]; });
                current['idcluster-upload'] = contents ? filename + ':' + contents.length : null;
                const norm = v => Array.isArray(v) ? [...v].sort((x, y) => x - y) : v;
                const same = (a, b) => JSON.stringify(norm(a)) === JSON.stringify(norm(b));
                return keys.map(id => same(current[id], applied[id]) ? hide : show);
            }
            """
            % tagged,
            [Output(f"{i}-pending", "style") for i in tagged + ["idcluster-upload"]],
            [Input(i, "value") for i in tagged]
            + [
                Input("idcluster-upload", "contents"),
                Input("idcluster-upload", "filename"),
                Input("applied-filters-store", "data"),
            ],
        )

        # Where the filter-dependent cluster traces sit in the figure (for incremental Apply).
        # Name rules mirror TraceRegistry: CLUSTER, MATCHED_PAIR and SELECTED_CLUSTER types.
        self.app.clientside_callback(
            """
            function(figure) {
                const data = (figure && figure.data) || [];
                const cluster = [];
                let hasCatred = false;
                data.forEach((trace, i) => {
                    const name = trace.name || '';
                    if (name.startsWith('CATRED')) { hasCatred = true; }
                    if (name.includes('Merged') || name.includes('Unmerged')
                        || name.includes('(Enhanced)') || name.includes('Cluster in Proximity')
                        || name === 'Matched Pair' || name === '__selected_cluster__') {
                        cluster.push(i);
                    }
                });
                return {cluster: cluster, has_catred: hasCatred, n: data.length};
            }
            """,
            Output("cluster-trace-index-store", "data"),
            Input("cluster-plot", "figure"),
        )

        # Only the selected algorithm's SNR filter is shown
        self.app.clientside_callback(
            """
            function(algorithm) {
                const show = {display: 'block'}, hide = {display: 'none'};
                return [algorithm === 'AMICO' ? hide : show, algorithm === 'PZWAV' ? hide : show];
            }
            """,
            [Output("snr-pzwav-container", "style"), Output("snr-amico-container", "style")],
            Input("algorithm-dropdown", "value"),
        )

        # Clear the uploaded cluster-ID list
        self.app.clientside_callback(
            """
            function(n) { return [null, null]; }
            """,
            [Output("idcluster-upload", "contents"), Output("idcluster-upload", "filename")],
            Input("idcluster-clear-button", "n_clicks"),
            prevent_initial_call=True,
        )

        for slider_id, readout_id in self.RANGE_SLIDER_READOUTS.items():
            # Two-way sync: slider <-> min/max number inputs
            self.app.clientside_callback(
                """
                function(value, lo, hi, min, max) {
                    const nu = window.dash_clientside.no_update;
                    const ctx = window.dash_clientside.callback_context;
                    const fromInput = ctx.triggered.some(
                        t => t.prop_id.endsWith('-lo.value') || t.prop_id.endsWith('-hi.value')
                    );
                    const round = x => Math.round(x * 100) / 100;
                    if (!fromInput) {
                        if (!value) { return [nu, nu, nu]; }
                        return [nu, round(value[0]), round(value[1])];
                    }
                    const num = (x, fallback) =>
                        (x === null || x === undefined || x === '' || isNaN(x)) ? fallback : Number(x);
                    let a = num(lo, value ? value[0] : min);
                    let b = num(hi, value ? value[1] : max);
                    a = Math.min(Math.max(a, min), max);
                    b = Math.min(Math.max(b, min), max);
                    if (a > b) { [a, b] = [b, a]; }
                    return [[a, b], a, b];
                }
                """,
                [
                    Output(slider_id, "value", allow_duplicate=True),
                    Output(f"{slider_id}-lo", "value"),
                    Output(f"{slider_id}-hi", "value"),
                ],
                [
                    Input(slider_id, "value"),
                    Input(f"{slider_id}-lo", "value"),
                    Input(f"{slider_id}-hi", "value"),
                ],
                [State(slider_id, "min"), State(slider_id, "max")],
                prevent_initial_call=True,
            )

            # Readout: selected cut, data range, and whether the plot reflects it
            self.app.clientside_callback(
                """
                function(value, min, max, disabled, applied) {
                    const span = (text, className) => ({
                        namespace: 'dash_html_components', type: 'Span',
                        props: {children: text, className: className}
                    });
                    if (disabled) {
                        return [[span('No data for this column', 'range-readout-range')],
                                'range-readout is-empty'];
                    }
                    if (!value) { return ['', 'range-readout']; }
                    const f = x => Number(x).toFixed(2);
                    const children = [
                        span(f(value[0]) + ' – ' + f(value[1]), 'range-readout-value'),
                        span('of ' + f(min) + ' – ' + f(max), 'range-readout-range'),
                    ];
                    const last = applied ? applied['%s'] : null;
                    const pending = last && (
                        Math.abs(last[0] - value[0]) > 1e-9 || Math.abs(last[1] - value[1]) > 1e-9
                    );
                    if (pending) {
                        children.push(span('Not applied', 'range-readout-flag'));
                        return [children, 'range-readout is-pending'];
                    }
                    return [children, 'range-readout'];
                }
                """
                % slider_id,
                [Output(readout_id, "children"), Output(readout_id, "className")],
                [
                    Input(slider_id, "value"),
                    Input(slider_id, "min"),
                    Input(slider_id, "max"),
                    Input(slider_id, "disabled"),
                    Input("applied-filters-store", "data"),
                ],
            )

    def _setup_button_text_callbacks(self):
        """Setup callbacks to update button text based on current settings"""

        @self.app.callback(
            Output("render-button", "children"),
            [Input("render-button", "n_clicks"), Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def update_main_button_text(n_clicks, algorithm):
            """Name the action: first render, then re-render for the selected algorithm"""
            if not n_clicks:
                return [html.I(className="fas fa-play me-2"), "Render clusters"]
            label = f"Re-render · {algorithm}" if algorithm else "Re-render"
            return [html.I(className="fas fa-redo me-2"), label]

    def _setup_button_state_callbacks(self):
        """Setup callbacks to enable/disable buttons based on conditions"""

        @self.app.callback(
            [
                Output("cluster-members-button", "disabled"),
                Output("tab-cluster-members-button", "disabled"),
            ],
            [Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_cluster_members_button(n_clicks):
            """Disable Cluster Members buttons if members catalog not configured or not yet rendered."""
            n_clicks = n_clicks or 0
            if n_clicks == 0:
                return True, True
            if self.config is None:
                return True, True
            members_xml = self.config.get_gluematchcat_members_xml()
            disabled = members_xml is None
            return disabled, disabled

        @self.app.callback(
            [
                Output("idcluster-clear-button", "style"),
                Output("idcluster-status-display", "children"),
            ],
            [
                Input("idcluster-upload", "contents"),
                Input("idcluster-upload", "filename"),
            ],
            prevent_initial_call=False,
        )
        def enable_idcluster_button(upload_contents, upload_filename):
            """Show the uploaded entry count and offer to clear the list."""
            hidden, shown = {"display": "none"}, {"display": "inline-block"}
            if not upload_contents or not upload_filename:
                return hidden, "No ID list uploaded"

            try:
                idcluster_array = get_idclusters_array(upload_contents, upload_filename)
                count = int(idcluster_array.size) if idcluster_array is not None else 0
                return shown, f"{count} cluster IDs from {upload_filename}"

            except Exception as error:
                return shown, f"Could not read {upload_filename}: {error}. Check it has one ID per line."

        @self.app.callback(
            Output("matching-clusters-switch", "disabled"),
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def toggle_matching_clusters_switch(algorithm):
            """Enable matching-clusters-switch only when algorithm is BOTH"""
            is_disabled = algorithm != "BOTH"
            print(
                f"🔄 Algorithm dropdown callback: algorithm={algorithm}, matching-switch-disabled={is_disabled}"
            )
            return is_disabled

        @self.app.callback(
            [
                Output("cltile-info-switch", "disabled"),
                Output("cltile-info-switch", "value"),
                Output("cltile-info-switch-help-text", "children"),
                Output("unmerged-clusters-switch", "disabled"),
                Output("unmerged-clusters-switch", "value"),
                Output("unmerged-clusters-switch-help-text", "children"),
            ],
            [Input("algorithm-dropdown", "value"), Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_individual_cltile_switches(algorithm, _render_clicks):
            """Disable CL-tile-dependent switches when individual tile data is unavailable."""
            return self._get_individual_cltile_switch_state(algorithm)

        @self.app.callback(
            [
                Output("browse-file-button", "disabled"),
                Output("browse-file-button", "title"),
            ],
            [Input("browse-file-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def disable_browse_button_if_no_config(n_clicks):
            """Disable browse button if gluematchcat_clusters is not configured"""
            if self.config is None:
                return True, "Configuration not available"
            
            # Check if gluematchcat_clusters is configured
            gluematchcat_clusters_xml = self.config.get_gluematchcat_clusters_xml()
            if gluematchcat_clusters_xml is None:
                return True, "GlueMatchCat XML file not configured in config.ini"
            
            return False, "Browse for file"

    def _get_individual_cltile_switch_state(self, algorithm):
        """Compute disabled/value/help text state for CL-tile-dependent switches."""
        is_available = True
        unavailable_message = self.NO_INDIVIDUAL_CLTILE_DATA_MESSAGE

        if self.data_loader and hasattr(self.data_loader, "get_individual_cltile_data_availability"):
            is_available, unavailable_message = self.data_loader.get_individual_cltile_data_availability(
                algorithm
            )

        if is_available:
            return (
                False,
                dash.no_update,
                self.DEFAULT_CLTILE_INFO_HELP_TEXT,
                False,
                dash.no_update,
                self.DEFAULT_UNMERGED_HELP_TEXT,
            )

        return True, False, unavailable_message, True, False, unavailable_message

    def _setup_catred_visibility_callback(self):
        """Setup clientside callback to show/hide CATRED controls based on catred-mode-switch"""
        self.app.clientside_callback(
            """
            function(catredEnabled) {
                // Convert boolean to display style
                let displayStyle = catredEnabled ? 'block' : 'none';
                
                // Return the display style for all 3 container elements
                return [
                    {display: displayStyle},
                    {display: displayStyle}, 
                    {display: displayStyle}
                ];
            }
            """,
            [
                Output("catred-threshold-container", "style"),
                Output("magnitude-limit-container", "style"),
            ],
            #  Output('catred-controls-container', 'style')],
            [Input("catred-mode-switch", "value")],
            prevent_initial_call=False,
        )

    def _setup_catred_render_color_callback(self):
        """Clientside callback: update CATRED MER Tile trace marker color without re-render.

        Uses JS spread to shallow-clone only the affected trace objects, leaving large
        data arrays (x, y, customdata) as shared references — no extra allocation.
        Triggered by the color picker; figure is read as State so figure changes alone
        do not re-trigger this callback.
        """
        self.app.clientside_callback(
            """
            function(markerColor, figure) {
                if (!figure || !figure.data || !markerColor) {
                    return window.dash_clientside.no_update;
                }
                var changed = false;
                var newData = figure.data.map(function(trace) {
                    if (trace.name &&
                            trace.name.indexOf('CATRED') !== -1 &&
                            trace.name.indexOf('MER Tile') !== -1) {
                        changed = true;
                        return Object.assign({}, trace, {
                            marker: Object.assign({}, trace.marker, {
                                line: Object.assign({}, trace.marker && trace.marker.line,
                                                    {color: markerColor})
                            })
                        });
                    }
                    return trace;
                });
                if (!changed) return window.dash_clientside.no_update;
                return Object.assign({}, figure, {data: newData});
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("catred-render-marker-color", "value"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

    def _setup_catred_box_color_callback(self):
        """Clientside callback: update CATRED Boxed trace marker color without re-render.

        Mirrors _setup_catred_render_color_callback but targets traces named
        'CATRED * - Boxed' (cluster-click box panel) instead of 'CATRED * MER Tile'.
        """
        self.app.clientside_callback(
            """
            function(markerColor, figure) {
                if (!figure || !figure.data || !markerColor) {
                    return window.dash_clientside.no_update;
                }
                var changed = false;
                var newData = figure.data.map(function(trace) {
                    if (trace.name &&
                            trace.name.indexOf('CATRED') !== -1 &&
                            trace.name.indexOf('Boxed') !== -1) {
                        changed = true;
                        return Object.assign({}, trace, {
                            marker: Object.assign({}, trace.marker, {
                                line: Object.assign({}, trace.marker && trace.marker.line,
                                                    {color: markerColor})
                            })
                        });
                    }
                    return trace;
                });
                if (!changed) return window.dash_clientside.no_update;
                return Object.assign({}, figure, {data: newData});
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("tab-catred-marker-color-picker", "value"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

    def _setup_collapsible_callbacks(self):
        """Open/close sidebar sections; the toggle's class drives the chevron"""
        for section in self.SIDEBAR_SECTIONS:
            self.app.clientside_callback(
                """
                function(n, isOpen) { return !isOpen; }
                """,
                Output(f"{section}-collapse", "is_open"),
                Input(f"{section}-toggle", "n_clicks"),
                State(f"{section}-collapse", "is_open"),
                prevent_initial_call=True,
            )
            self.app.clientside_callback(
                """
                function(isOpen) {
                    return isOpen
                        ? ['section-toggle is-open', 'sidebar-section is-open']
                        : ['section-toggle', 'sidebar-section'];
                }
                """,
                [Output(f"{section}-toggle", "className"), Output(f"{section}-section", "className")],
                Input(f"{section}-collapse", "is_open"),
            )

    def _setup_config_display_callback(self):
        """Setup callback to display configuration parameters"""

        @self.app.callback(
            [
                Output("config-merged-catalog", "children"),
                Output("config-detintile-list", "children"),
            ],
            [Input("render-button", "n_clicks"), Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def display_config_info(n_clicks, algorithm):
            """Display current configuration parameters"""
            if self.config is None:
                return (
                    html.Div(
                        [
                            dbc.Badge("Not Available", color="warning", className="me-2"),
                            html.Span("Configuration not loaded", className="text-muted"),
                        ]
                    ),
                    html.Div(
                        [
                            dbc.Badge("Not Available", color="warning", className="me-2"),
                            html.Span("Configuration not loaded", className="text-muted"),
                        ]
                    ),
                )

            try:
                # Get merged catalog file
                gluematchcat_path = self.config.get_gluematchcat_clusters_xml()
                
                merged_catalog_display = None
                if gluematchcat_path and os.path.exists(gluematchcat_path):
                    # Show abbreviated path (last 2 segments + filename)
                    path_parts = Path(gluematchcat_path).parts
                    if len(path_parts) > 2:
                        short_path = str(Path(*path_parts[-2:]))
                    else:
                        short_path = os.path.basename(gluematchcat_path)
                    
                    merged_catalog_display = html.Div(
                        [
                            dbc.Badge("GlueMatchCat", color="success", className="me-2"),
                            html.Span(
                                short_path,
                                className="text-primary font-monospace small",
                                title=gluematchcat_path,
                                style={"cursor": "help"},
                            ),
                        ]
                    )
                else:
                    # Try algorithm-specific merged catalog
                    try:
                        mergedet_files = self.config.get_mergedetcat_xml_files(algorithm)
                        if mergedet_files:
                            # Get the first available file
                            first_key = next(iter(mergedet_files))
                            mergedet_path = mergedet_files[first_key]
                            
                            if mergedet_path and os.path.exists(mergedet_path):
                                path_parts = Path(mergedet_path).parts
                                if len(path_parts) > 2:
                                    short_path = str(Path(*path_parts[-2:]))
                                else:
                                    short_path = os.path.basename(mergedet_path)
                                
                                merged_catalog_display = html.Div(
                                    [
                                        dbc.Badge(f"MergeDetCat ({algorithm})", color="info", className="me-2"),
                                        html.Span(
                                            short_path,
                                            className="text-primary font-monospace small",
                                            title=mergedet_path,
                                            style={"cursor": "help"},
                                        ),
                                    ]
                                )
                            else:
                                merged_catalog_display = html.Div(
                                    [
                                        dbc.Badge("Not Found", color="danger", className="me-2"),
                                        html.Span("File configured but missing", className="text-muted small"),
                                    ]
                                )
                        else:
                            merged_catalog_display = html.Div(
                                [
                                    dbc.Badge("Not Configured", color="warning", className="me-2"),
                                    html.Span("No merged catalog configured", className="text-muted small"),
                                ]
                            )
                    except Exception as e:
                        merged_catalog_display = html.Div(
                            [
                                dbc.Badge("Error", color="danger", className="me-2"),
                                html.Span(f"Error: {str(e)}", className="text-danger small"),
                            ]
                        )

                # Get DetInTile list files
                detintile_display = None
                try:
                    detintile_files = self.config.get_detintile_list_files(algorithm)
                    if detintile_files:
                        detintile_items = []
                        for key, json_path in detintile_files.items():
                            if json_path and os.path.exists(json_path):
                                path_parts = Path(json_path).parts
                                if len(path_parts) > 2:
                                    short_path = str(Path(*path_parts[-2:]))
                                else:
                                    short_path = os.path.basename(json_path)
                                
                                # Extract algorithm name from key
                                algo_name = key.replace("detintile_", "").replace("_list", "").upper()
                                
                                detintile_items.append(
                                    html.Div(
                                        [
                                            dbc.Badge(algo_name, color="primary", className="me-2"),
                                            html.Span(
                                                short_path,
                                                className="text-info font-monospace small",
                                                title=json_path,
                                                style={"cursor": "help"},
                                            ),
                                        ],
                                        className="mb-1",
                                    )
                                )
                            else:
                                algo_name = key.replace("detintile_", "").replace("_list", "").upper()
                                detintile_items.append(
                                    html.Div(
                                        [
                                            dbc.Badge(algo_name, color="danger", className="me-2"),
                                            html.Span("File missing", className="text-muted small"),
                                        ],
                                        className="mb-1",
                                    )
                                )
                        
                        detintile_display = html.Div(detintile_items)
                    else:
                        detintile_display = html.Div(
                            [
                                dbc.Badge("Not Configured", color="warning", className="me-2"),
                                html.Span("No tile list configured", className="text-muted small"),
                            ]
                        )
                except Exception as e:
                    detintile_display = html.Div(
                        [
                            dbc.Badge("Error", color="danger", className="me-2"),
                            html.Span(f"Error: {str(e)}", className="text-danger small"),
                        ]
                    )

                return merged_catalog_display, detintile_display

            except Exception as e:
                error_display = html.Div(
                    [
                        dbc.Badge("Error", color="danger", className="me-2"),
                        html.Span(str(e), className="text-danger small"),
                    ]
                )
                return error_display, error_display

    def _setup_file_configuration_callback(self):
        """Setup callback to display current gluematchcat file"""

        @self.app.callback(
            Output("gluematchcat-file-display", "value"),
            [Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def display_current_file(n_clicks):
            """Display current gluematchcat XML file basename"""
            if self.config is None:
                return "Config not available"

            try:
                gluematchcat_path = self.config.get_gluematchcat_clusters_xml()
                if gluematchcat_path and os.path.exists(gluematchcat_path):
                    return os.path.basename(gluematchcat_path)
                else:
                    return "No file configured"
            except Exception as e:
                return f"Error: {str(e)}"

    def _setup_file_browser_callbacks(self):
        """Setup callbacks for file browser modal"""

        # Open file browser modal when browse button is clicked
        @self.app.callback(
            [
                Output("file-browser-modal", "is_open"),
                Output("file-browser-directory", "value"),
            ],
            [
                Input("browse-file-button", "n_clicks"),
                Input("file-browser-close", "n_clicks"),
                Input("file-browser-cancel", "n_clicks"),
                Input("file-browser-select", "n_clicks"),
            ],
            [State("file-browser-modal", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_file_browser(browse_clicks, close_clicks, cancel_clicks, select_clicks, is_open):
            """Toggle file browser modal and initialize directory"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if button_id == "browse-file-button":
                # Check if gluematchcat_clusters is configured
                if self.config is None or self.config.get_gluematchcat_clusters_xml() is None:
                    # Don't open modal if not configured
                    return False, dash.no_update
                
                # Get default directory from config
                default_dir = ""
                if self.config and hasattr(self.config, "gluematchcat_dir"):
                    default_dir = self.config.gluematchcat_dir or ""
                return True, default_dir
            else:
                # Close modal
                return False, dash.no_update

        # List files when directory changes or refresh is clicked
        @self.app.callback(
            Output("file-browser-list", "children"),
            [
                Input("file-browser-directory", "value"),
                Input("file-browser-refresh", "n_clicks"),
            ],
            prevent_initial_call=False,
        )
        def list_files(directory, refresh_clicks):
            """List XML files in the specified directory"""
            if not directory or not os.path.exists(directory):
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                        "Invalid or empty directory path",
                    ],
                    className="text-muted text-center p-3",
                )

            try:
                # Find all XML files in directory
                xml_files = []
                leveldeep = 0
                while leveldeep <= 2:  # Search up to 2 levels deep
                    pattern = os.path.join(directory, *["*"] * leveldeep, "unified_clusters*.xml")
                    xml_files.extend(glob.glob(pattern))
                    leveldeep += 1

                if not xml_files:
                    return html.Div(
                        [
                            html.I(className="fas fa-folder-open text-muted me-2"),
                            "No XML files found in this directory",
                        ],
                        className="text-muted text-center p-3",
                    )

                # Create clickable list of files
                file_list = []
                for xml_file in sorted(xml_files):
                    filename = os.path.relpath(xml_file, directory)
                    file_list.append(
                        dbc.Button(
                            [
                                html.I(className="fas fa-file-code me-2"),
                                filename,
                            ],
                            id={"type": "file-item", "index": xml_file},
                            color="light",
                            className="w-100 text-start mb-2",
                            size="sm",
                            n_clicks=0,
                        )
                    )

                return html.Div(file_list)

            except Exception as e:
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-circle text-danger me-2"),
                        f"Error reading directory: {str(e)}",
                    ],
                    className="text-danger p-3",
                )

        # Store selected file and enable select button
        @self.app.callback(
            [
                Output("selected-file-path", "data"),
                Output("file-browser-select", "disabled"),
            ],
            [Input({"type": "file-item", "index": ALL}, "n_clicks")],
            [State({"type": "file-item", "index": ALL}, "id")],
            prevent_initial_call=True,
        )
        def select_file(n_clicks_list, button_ids):
            """Store selected file path when a file is clicked"""
            ctx = callback_context
            if not ctx.triggered or not any(n_clicks_list):
                return dash.no_update, dash.no_update

            # Find which button was clicked
            triggered_id = ctx.triggered_id
            if triggered_id and isinstance(triggered_id, dict):
                selected_path = triggered_id.get("index")
                if selected_path:
                    return selected_path, False

            return dash.no_update, dash.no_update

        # Apply selected file to input when Select button is clicked
        @self.app.callback(
            Output("gluematchcat-file-input", "value"),
            [Input("file-browser-select", "n_clicks")],
            [State("selected-file-path", "data")],
            prevent_initial_call=True,
        )
        def apply_selected_file(select_clicks, selected_path):
            """Apply selected file path to the input field"""
            if selected_path:
                return selected_path
            return dash.no_update

        # Enable apply button when file input changes
        @self.app.callback(
            Output("apply-file-config-button", "disabled"),
            [Input("gluematchcat-file-input", "value")],
            prevent_initial_call=False,
        )
        def enable_apply_button(file_path):
            """Enable apply button when a valid file path is entered"""
            if file_path and file_path.strip() and file_path.endswith(".xml"):
                return False
            return True

        # Handle apply button click
        @self.app.callback(
            [
                Output("file-config-status", "children"),
                Output("gluematchcat-file-display", "value", allow_duplicate=True),
            ],
            [Input("apply-file-config-button", "n_clicks")],
            [State("gluematchcat-file-input", "value")],
            prevent_initial_call=True,
        )
        def apply_file_config(n_clicks, file_path):
            """Apply the new file configuration"""
            if not file_path or not file_path.strip():
                return (
                    html.Div(
                        [
                            html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                            "No file path provided",
                        ],
                        className="text-warning",
                    ),
                    dash.no_update,
                )

            # Validate file exists
            if not os.path.exists(file_path):
                return (
                    html.Div(
                        [
                            html.I(className="fas fa-exclamation-circle text-danger me-2"),
                            f"File not found: {os.path.basename(file_path)}",
                        ],
                        className="text-danger",
                    ),
                    dash.no_update,
                )

            # Validate it's an XML file
            if not file_path.endswith(".xml"):
                return (
                    html.Div(
                        [
                            html.I(className="fas fa-exclamation-circle text-danger me-2"),
                            "File must be an XML file",
                        ],
                        className="text-danger",
                    ),
                    dash.no_update,
                )

            # Update config if available
            if self.config:
                try:
                    # Update the config parser
                    if not self.config.config_parser.has_section("files"):
                        self.config.config_parser.add_section("files")
                    self.config.config_parser.set("files", "gluematchcat_clusters", file_path)

                    # Save to config file in tmp directory
                    config_path = Path(self.config._config_file_used)
                    
                    # Determine the base config file (remove _temp if present)
                    if config_path.name.endswith("_temp.ini"):
                        base_stem = config_path.stem.replace("_temp", "")
                        # Get parent of current file, and if it's 'tmp', go one level up
                        if config_path.parent.name == "tmp":
                            config_parent = config_path.parent.parent
                        else:
                            config_parent = config_path.parent
                    else:
                        base_stem = config_path.stem
                        config_parent = config_path.parent
                    
                    # Always place temp config in tmp directory
                    tmp_dir = config_parent / "tmp"
                    tmp_dir.mkdir(exist_ok=True)
                    newconfigfile_path = str(tmp_dir / f"{base_stem}_temp.ini")
                    with open(newconfigfile_path, "w") as f:
                        self.config.config_parser.write(f)

                    # Clear ALL caches to force reload with new file
                    if self.data_loader:
                        # Clear in-memory cache
                        self.data_loader.data_cache.clear()
                        print(f"✓ Cleared in-memory data cache")

                        # Clear disk cache entries for merged catalog
                        if hasattr(self.data_loader, "cached") and self.data_loader.cached:
                            cache_keys_to_remove = []
                            for key in self.data_loader.cached.keys():
                                if "merged_catalog" in key:
                                    cache_keys_to_remove.append(key)
                            for key in cache_keys_to_remove:
                                del self.data_loader.cached[key]
                                print(f"✓ Cleared disk cache entry: {key}")

                    return html.Div(
                        [
                            html.I(className="fas fa-check-circle text-success me-2"),
                            f"Configuration updated! Click 'Render' to reload data with: {os.path.basename(file_path)}",
                        ],
                        className="text-success",
                    ), os.path.basename(file_path)

                except Exception as e:
                    return (
                        html.Div(
                            [
                                html.I(className="fas fa-exclamation-circle text-danger me-2"),
                                f"Error updating config: {str(e)}",
                            ],
                            className="text-danger",
                        ),
                        dash.no_update,
                    )
            else:
                return html.Div(
                    [
                        html.I(className="fas fa-info-circle text-info me-2"),
                        "Config not available - changes will not persist",
                    ],
                    className="text-info",
                ), os.path.basename(file_path)

    # Helper functions

    # def _count_uploaded_id_entries(self, upload_contents, filename):
    #     """Count uploaded entries for txt/dat files or CSV values."""
    #     if not upload_contents or not filename:
    #         return 0

    #     _, content_string = upload_contents.split(",", 1)
    #     decoded_text = base64.b64decode(content_string).decode("utf-8", errors="ignore")
    #     suffix = Path(filename).suffix.lower()

    #     if suffix in {".txt", ".dat"}:
    #         return sum(1 for line in decoded_text.splitlines() if line.strip())

    #     if suffix == ".csv":
    #         reader = csv.reader(io.StringIO(decoded_text))
    #         return sum(1 for row in reader for value in row if str(value).strip())

    def _setup_status_toast_dismiss_callback(self):
        """Toggle button minimizes the status-info toast to a blob; content stays mounted so it can be restored.
        New content arriving auto-restores it from the minimized state."""
        self.app.clientside_callback(
            """
            function(n_clicks, children, isMinimized) {
                const trig = window.dash_clientside.callback_context.triggered[0].prop_id;
                if (trig.startsWith('status-info.')) {
                    return children ? false : window.dash_clientside.no_update;
                }
                return !isMinimized;
            }
            """,
            Output("status-toast-minimized-store", "data"),
            [Input("status-info-toggle", "n_clicks"), Input("status-info", "children")],
            State("status-toast-minimized-store", "data"),
            prevent_initial_call=True,
        )

        self.app.clientside_callback(
            """
            function(isMinimized) {
                return isMinimized ? 'status-toast-container status-toast-minimized' : 'status-toast-container';
            }
            """,
            Output("status-toast-outer", "className"),
            Input("status-toast-minimized-store", "data"),
        )

    def _setup_getting_started_callback(self):
        """Auto-open onboarding modal for first-time users (onboarding-seen-store persists in localStorage)."""
        self.app.clientside_callback(
            "function(seen) { return !seen; }",
            Output("getting-started-modal", "is_open"),
            Input("onboarding-seen-store", "data"),
        )

        self.app.clientside_callback(
            "function(n_clicks) { return n_clicks ? true : window.dash_clientside.no_update; }",
            Output("getting-started-modal", "is_open", allow_duplicate=True),
            Input("getting-started-open", "n_clicks"),
            prevent_initial_call=True,
        )

        self.app.clientside_callback(
            "function(c1, c2) { return (c1 || c2) ? [false, true] : [window.dash_clientside.no_update, window.dash_clientside.no_update]; }",
            [Output("getting-started-modal", "is_open", allow_duplicate=True),
             Output("onboarding-seen-store", "data")],
            [Input("getting-started-close", "n_clicks"), Input("getting-started-close-footer", "n_clicks")],
            prevent_initial_call=True,
        )

    def _setup_tutorial_tour_callback(self):
        """Interactive guided tour (driver.js), lazy-loaded from CDN on first click."""
        self.app.clientside_callback(
            """
            function(n_clicks) {
                if (!n_clicks) return window.dash_clientside.no_update;

                function runTour() {
                    var d = window.driver.js.driver({
                        showProgress: true,
                        allowClose: true,
                        steps: [
                            { element: '#cluster-plot', popover: { title: 'Main plot', description: 'Pan, zoom and click a cluster to select it.', side: 'bottom' } },
                            { element: '#view-mode-btn-group', popover: { title: 'View modes', description: 'Switch between the Standard scatter view and Aladin sky view (Aladin enables once you zoom to a single cluster).', side: 'bottom' } },
                            { element: '#render-button', popover: { title: 'Render', description: 'Draw the catalog for the selected algorithm. Click again to re-render.', side: 'right' } },
                            { element: '#clusters-settings-toggle', popover: { title: 'Catalog', description: 'Choose the detection algorithm, CL-tile information and unmerged clusters.', side: 'right' } },
                            { element: '#filters-settings-toggle', popover: { title: 'Filters', description: 'Set redshift, SNR, richness, cluster-ID and matched-cluster options, then press Apply filters at the bottom of the section.', side: 'right' } },
                            { element: '#mask-controls-toggle', popover: { title: 'Mask', description: 'Toggle the CATRED source overlay and Healpix mask.', side: 'right' } },
                            { element: '#image-controls-toggle', popover: { title: 'Mosaic', description: 'Load survey imagery for the current zoomed view.', side: 'right' } },
                            { element: '#display-options-toggle', popover: { title: 'Display', description: 'Toggle polygon/MER overlays and other display settings.', side: 'right' } },
                            { element: '#status-info-toggle', popover: { title: 'Status', description: 'Status messages show up here; click to restore if minimized.', side: 'left' } },
                            { element: '#getting-started-open', popover: { title: 'Need more detail?', description: 'Reopen the full Getting Started guide anytime.', side: 'bottom' } },
                        ]
                    });
                    d.drive();
                }

                if (!document.getElementById('driverjs-css')) {
                    var link = document.createElement('link');
                    link.id = 'driverjs-css'; link.rel = 'stylesheet';
                    link.href = 'https://cdn.jsdelivr.net/npm/driver.js@1/dist/driver.css';
                    document.head.appendChild(link);
                }
                if (!document.getElementById('driverjs-js')) {
                    var script = document.createElement('script');
                    script.id = 'driverjs-js';
                    script.src = 'https://cdn.jsdelivr.net/npm/driver.js@1/dist/driver.js.iife.js';
                    script.onload = runTour;
                    document.head.appendChild(script);
                    return window.dash_clientside.no_update;
                }

                runTour();
                return window.dash_clientside.no_update;
            }
            """,
            Output("tour-init-dummy", "children"),
            Input("tutorial-tour-button", "n_clicks"),
            prevent_initial_call=True,
        )

    def _setup_view_mode_callbacks(self):
        """Clientside callbacks for switching between Standard (Plotly) and Aladin views."""

        # Toggle button clicks → update view-mode-store
        self.app.clientside_callback(
            """
            function(plotlyClicks, aladinClicks, currentMode) {
                const triggered = window.dash_clientside.callback_context.triggered;
                if (!triggered || triggered.length === 0) {
                    return window.dash_clientside.no_update;
                }
                const prop = triggered[0].prop_id;
                var next = window.dash_clientside.no_update;
                if (prop.includes('view-mode-plotly-btn')) next = 'plotly';
                if (prop.includes('view-mode-aladin-btn')) next = 'aladin';
                if (next !== window.dash_clientside.no_update) {
                    try { fetch('/log', {method:'POST', body:'[view-toggle] ' + currentMode + ' → ' + next}); } catch(e) {}
                }
                return next;
            }
            """,
            Output("view-mode-store", "data"),
            [Input("view-mode-plotly-btn", "n_clicks"),
             Input("view-mode-aladin-btn", "n_clicks")],
            State("view-mode-store", "data"),
            prevent_initial_call=True,
        )

        # image-source-radio (in Mosaic sidebar) → view-mode-store
        self.app.clientside_callback(
            """
            function(radioVal) {
                if (radioVal === 'aladin') return 'aladin';
                if (radioVal === 'mosaic') return 'plotly';
                return window.dash_clientside.no_update;
            }
            """,
            Output("view-mode-store", "data", allow_duplicate=True),
            Input("image-source-radio", "value"),
            prevent_initial_call=True,
        )

        # view-mode-store → show/hide containers, button styles, mosaic controls, interval
        self.app.clientside_callback(
            """
            function(mode) {
                const isPlotly = mode === 'plotly';
                const isAladin = mode === 'aladin';
                const plotlyStyle = {display: isPlotly ? 'block' : 'none'};
                const aladinStyle = {display: isAladin ? 'block' : 'none'};
                const plotlyOutline = !isPlotly;
                const aladinOutline = !isAladin;
                const aladinIntervalDisabled = !isAladin;
                const merControlsStyle = {display: isAladin ? 'none' : 'block'};
                const surveyDropdownStyle = {display: isAladin ? 'block' : 'none'};
                const radioVal = isAladin ? 'aladin' : 'mosaic';
                // Show skeleton immediately when switching to Aladin; JS bridge hides it on init
                const skeletonStyle = isAladin
                    ? {display: 'flex', position: 'absolute', inset: '0', zIndex: '10', borderRadius: '8px'}
                    : {display: 'none'};
                return [plotlyStyle, aladinStyle, plotlyOutline, aladinOutline,
                        aladinIntervalDisabled, merControlsStyle, surveyDropdownStyle, radioVal,
                        skeletonStyle];
            }
            """,
            [Output("plotly-view-container", "style"),
             Output("aladin-view-container", "style"),
             Output("view-mode-plotly-btn", "outline"),
             Output("view-mode-aladin-btn", "outline"),
             Output("aladin-click-poll-interval", "disabled"),
             Output("mer-mosaic-controls", "style"),
             Output("aladin-survey-dropdown", "style"),
             Output("image-source-radio", "value"),
             Output("aladin-skeleton", "style")],
            Input("view-mode-store", "data"),
        )

        # Count cluster points in viewport → enable/disable Aladin button + build overlay data
        # Clientside: zero server round-trip. Reads cluster/CATRED directly from figure.data traces.
        self.app.clientside_callback(
            """
            function(relayoutData, viewMode, figure, survey, maskHipsPath) {
                var NO_UPDATE = window.dash_clientside.no_update;
                if (!figure || !figure.layout) return [true, NO_UPDATE, NO_UPDATE];

                // Resolve viewport: prefer relayoutData values, fall back to figure layout
                var raMin, raMax, decMin, decMax;
                if (relayoutData) {
                    if ('xaxis.range[0]' in relayoutData) {
                        raMin = relayoutData['xaxis.range[0]']; raMax = relayoutData['xaxis.range[1]'];
                        decMin = relayoutData['yaxis.range[0]']; decMax = relayoutData['yaxis.range[1]'];
                    } else if (relayoutData['xaxis.range']) {
                        raMin = relayoutData['xaxis.range'][0]; raMax = relayoutData['xaxis.range'][1];
                        decMin = relayoutData['yaxis.range'][0]; decMax = relayoutData['yaxis.range'][1];
                    }
                }
                if (raMin == null) {
                    var layout = figure.layout;
                    var xr = (layout.xaxis || {}).range;
                    var yr = (layout.yaxis || {}).range;
                    if (!xr || !yr) return [true, NO_UPDATE, NO_UPDATE];
                    raMin = xr[0]; raMax = xr[1]; decMin = yr[0]; decMax = yr[1];
                }
                var tmp;
                if (raMin > raMax) { tmp = raMin; raMin = raMax; raMax = tmp; }
                if (decMin > decMax) { tmp = decMin; decMin = decMax; decMax = tmp; }

                var raCtr = (raMin + raMax) / 2.0;
                var decCtr = (decMin + decMax) / 2.0;
                var fov = Math.max(Math.abs(raMax - raMin), Math.abs(decMax - decMin));
                var fov2 = fov * 2.0;
                var cosD = Math.cos(decCtr * Math.PI / 180.0);

                // Count clusters in viewport and collect all within 2×FOV for Aladin
                var count = 0;
                var clusterPts = [];  // {ra, dec, name}
                var catredPts = [];
                var maskPolygons = [];  // [[ra,dec], ...] per polygon segment (kept for legacy)
                var maskMocPixels = [];  // flat int array of HEALPix pixel IDs (order 14)
                var membersPts = [];

                (figure.data || []).forEach(function(trace) {
                    var name = (trace.name || '');
                    var isCatred = name.indexOf('CATRED') === 0;
                    var isMask = name.indexOf('Mask overlay') === 0 || name.indexOf('Inverted mask overlay') === 0;
                    var isMembers = name.indexOf('Members (ID') === 0;
                    var isCluster = !isCatred && !isMask && !isMembers && (
                        name.indexOf('Merged') >= 0 || name.indexOf('PZWAV') >= 0 || name.indexOf('AMICO') >= 0
                    );
                    // Exclude glow halos (no cluster-count suffix and contain 'near CATRED')
                    if (isCluster && name.indexOf('in CATRED region') >= 0) isCluster = false;
                    if (isCluster && name.indexOf('near CATRED') >= 0 && name.indexOf(' clusters') < 0) isCluster = false;

                    var xs = trace.x || [];
                    var ys = trace.y || [];
                    var texts = trace.text || [];

                    if (isCluster) {
                        for (var i = 0; i < xs.length; i++) {
                            var ra = xs[i], dec = ys[i];
                            if (ra == null || dec == null) continue;
                            // Count clusters strictly in viewport
                            if (ra >= raMin && ra <= raMax && dec >= decMin && dec <= decMax) count++;
                            // Collect all within 2×FOV for Aladin overlay
                            var dra = (ra - raCtr) * cosD;
                            var ddec = dec - decCtr;
                            if (Math.sqrt(dra*dra + ddec*ddec) <= fov2) {
                                var lbl = (typeof texts[i] === 'string') ? texts[i] : '';
                                clusterPts.push({ra: ra, dec: dec, name: lbl});
                            }
                        }
                    } else if (isCatred) {
                        for (var i = 0; i < xs.length; i++) {
                            var ra = xs[i], dec = ys[i];
                            if (ra == null || dec == null) continue;
                            var dra = (ra - raCtr) * cosD;
                            var ddec = dec - decCtr;
                            if (Math.sqrt(dra*dra + ddec*ddec) <= fov2) {
                                catredPts.push({ra: ra, dec: dec, name: 'CATRED'});
                            }
                        }
                    } else if (isMask) {
                        // Split null-separated polygon segments
                        var poly = [];
                        for (var i = 0; i < xs.length; i++) {
                            if (xs[i] == null) {
                                if (poly.length > 1) maskPolygons.push(poly);
                                poly = [];
                            } else {
                                poly.push([xs[i], ys[i]]);
                            }
                        }
                        if (poly.length > 1) maskPolygons.push(poly);
                    } else if (name.indexOf('Mask aladin moc') === 0 || name.indexOf('Inverted mask aladin moc') === 0) {
                        // Invisible trace carrying comma-separated HEALPix pixel IDs
                        var txt = (typeof trace.text === 'string') ? trace.text : '';
                        if (txt) {
                            txt.split(',').forEach(function(s) {
                                var id = parseInt(s, 10);
                                if (!isNaN(id)) maskMocPixels.push(id);
                            });
                        }
                    } else if (isMembers) {
                        for (var i = 0; i < xs.length; i++) {
                            var ra = xs[i], dec = ys[i];
                            if (ra == null || dec == null) continue;
                            var dra = (ra - raCtr) * cosD;
                            var ddec = dec - decCtr;
                            if (Math.sqrt(dra*dra + ddec*ddec) <= fov2) {
                                var lbl = (typeof texts[i] === 'string') ? texts[i] : '';
                                membersPts.push({ra: ra, dec: dec, name: lbl});
                            }
                        }
                    }
                });

                var disabled = count !== 1;
                var radioOptions = [
                    {label: ' MER Mosaic', value: 'mosaic'},
                    {label: ' Aladin Sky', value: 'aladin', disabled: disabled}
                ];

                // Build overlay for Aladin (pre-computed, no server needed)
                var overlayData = {
                    clusters: clusterPts,
                    catred: catredPts,
                    mask_polygons: maskPolygons,
                    mask_moc_pixels: maskMocPixels,
                    mask_hips_path: maskHipsPath || null,
                    members: membersPts,
                    viewport: {ra: raCtr, dec: decCtr, fov: fov},
                    survey: survey || 'P/DESI-Legacy-Surveys/DR10/color'
                };

                return [disabled, radioOptions, overlayData];
            }
            """,
            [Output("view-mode-aladin-btn", "disabled"),
             Output("image-source-radio", "options"),
             Output("aladin-overlay-data-store", "data")],
            [Input("cluster-plot", "relayoutData"),
             Input("view-mode-store", "data")],
            [State("cluster-plot", "figure"),
             State("aladin-survey-dropdown", "value"),
             State("mask-hips-path-store", "data")],
            prevent_initial_call=False,
        )

        # Populate mask-hips-path-store: convert filesystem path → HTTP URL served by Flask.
        _fs_path = getattr(self.config, "mask_hips_path", None) if self.config else None
        import os as _os
        mask_hips_url = "/hips/mask" if (_fs_path and _os.path.isdir(_fs_path)) else None

        @self.app.callback(
            Output("mask-hips-path-store", "data"),
            Input("aladin-preload-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def _init_mask_hips_path_store(_n):
            return mask_hips_url

        # Aladin Lite JS bridge: lazy-load CDN, init viewer, push catalog overlays.
        # Mask is added as a HiPS overlay image layer (no server data needed).
        self.app.clientside_callback(
            """
            function(overlayData, viewMode) {
                function dbg(msg) {
                    try { fetch('/log', {method:'POST', body: '[aladin-bridge] ' + msg}); } catch(e) {}
                }
                if (!overlayData) { dbg('skip: no overlayData, viewMode=' + viewMode); return window.dash_clientside.no_update; }
                // Only render when Aladin mode is active.
                if (viewMode !== 'aladin') { dbg('skip: viewMode=' + viewMode); return window.dash_clientside.no_update; }

                // If the view-mode-store triggered this callback (user switched to Aladin),
                // clear the dedup fingerprint so re-entry always forces a full re-init even
                // when the viewport/survey hasn't changed since the last Aladin visit.
                var triggered = window.dash_clientside.callback_context.triggered || [];
                var modeTriggered = triggered.some(function(t) {
                    return t.prop_id.indexOf('view-mode-store') >= 0;
                });
                dbg('FIRED viewMode=' + viewMode + ' modeTriggered=' + modeTriggered + ' lastFp=' + (window._aladinLastFp||'null') + ' hasInstance=' + !!window._aladinInstance);
                if (modeTriggered) {
                    dbg('clearing _aladinLastFp (mode switch)');
                    window._aladinLastFp = null;
                }

                function doAladinInit(data) {
                    var vp  = data.viewport || {};
                    var ra  = vp.ra  != null ? vp.ra  : 180.0;
                    var dec = vp.dec != null ? vp.dec : 0.0;
                    var fov = vp.fov != null ? vp.fov : 1.0;
                    var survey = data.survey || 'P/DESI-Legacy-Surveys/DR10/color';

                    function setupCatalogs(aladin) {
                        // Overlay registry: track references for explicit removal
                        window._aladinOverlays = window._aladinOverlays || {
                            maskHips: null, maskMoc: null, catalogs: []
                        };
                        var reg = window._aladinOverlays;

                        // Remove previously tracked catalogs
                        reg.catalogs.forEach(function(cat) {
                            try { aladin.removeLayer(cat); } catch(e) {}
                        });
                        reg.catalogs = [];

                        // Remove previously tracked MOC
                        if (reg.maskMoc) {
                            try { aladin.removeLayer(reg.maskMoc); } catch(e) {}
                            reg.maskMoc = null;
                        }

                        // Hide skeleton
                        var sk = document.getElementById('aladin-skeleton');
                        if (sk) sk.style.display = 'none';

                        // Mask overlay: HiPS image layer (priority) or MOC fallback
                        if (data.mask_hips_path && !reg.maskHips) {
                            try {
                                var hipsLayer = A.imageHiPS(data.mask_hips_path, {name: 'Mask HiPS', opacity: 0.5});
                                aladin.addNewImageLayer(hipsLayer);
                                reg.maskHips = hipsLayer;
                            } catch(e) { console.warn('[Aladin] HiPS mask layer failed:', e); }
                        } else if (!data.mask_hips_path && data.mask_moc_pixels && data.mask_moc_pixels.length > 0) {
                            try {
                                var mocData = {};
                                mocData['14'] = data.mask_moc_pixels;
                                var moc = A.MOCFromJSON(mocData, {
                                    name: 'Mask MOC',
                                    color: 'white',
                                    opacity: 0.5,
                                    fill: true,
                                    fillColor: 'white'
                                });
                                aladin.addMOC(moc);
                                reg.maskMoc = moc;
                            } catch(e) { console.warn('[Aladin] MOC mask overlay failed:', e); }
                        }

                        // Build source arrays
                        var pzwavSrcs = [], amicoSrcs = [];
                        (data.clusters || []).forEach(function(r) {
                            var name = (r.name || '').toUpperCase();
                            var src = A.source(r.ra, r.dec, {name: r.name || ''});
                            if (name.indexOf('AMICO') >= 0) { amicoSrcs.push(src); }
                            else { pzwavSrcs.push(src); }
                        });
                        var catredSrcs = (data.catred || []).map(function(r) {
                            return A.source(r.ra, r.dec, {name: r.name || 'CATRED'});
                        });
                        var membersSrcs = (data.members || []).map(function(r) {
                            return A.source(r.ra, r.dec, {name: r.name || 'Member'});
                        });

                        // Only add catalogs that have data (avoids empty entries in stack)
                        if (pzwavSrcs.length) {
                            var pzwavCat = A.catalog({name: 'PZWAV Clusters', color: '#ff6600', shape: 'x', sourceSize: 14});
                            pzwavCat.addSources(pzwavSrcs);
                            aladin.addCatalog(pzwavCat);
                            reg.catalogs.push(pzwavCat);
                        }
                        if (amicoSrcs.length) {
                            var amicoCat = A.catalog({name: 'AMICO Clusters', color: '#ff6600', shape: 'cross', sourceSize: 14});
                            amicoCat.addSources(amicoSrcs);
                            aladin.addCatalog(amicoCat);
                            reg.catalogs.push(amicoCat);
                        }
                        if (catredSrcs.length) {
                            var catredCat = A.catalog({name: 'CATRED', color: '#00ffff', shape: 'circle', sourceSize: 8});
                            catredCat.addSources(catredSrcs);
                            aladin.addCatalog(catredCat);
                            reg.catalogs.push(catredCat);
                        }
                        if (membersSrcs.length) {
                            var membersCat = A.catalog({name: 'Members', color: '#FFD700', shape: 'rhomb', sourceSize: 10});
                            membersCat.addSources(membersSrcs);
                            aladin.addCatalog(membersCat);
                            reg.catalogs.push(membersCat);
                        }
                    }

                    var doInit = function() {
                        // Dedup: skip re-render if viewport+survey unchanged (double-fire guard)
                        var fp = ra.toFixed(4) + ',' + dec.toFixed(4) + ',' + fov.toFixed(4) + ',' + survey;
                        dbg('doInit fp=' + fp + ' lastFp=' + (window._aladinLastFp||'null') + ' hasInstance=' + !!window._aladinInstance);
                        if (fp === window._aladinLastFp) {
                            dbg('DEDUP SKIP: fp unchanged');
                            return;
                        }
                        window._aladinLastFp = fp;

                        if (window._aladinInstance) {
                            dbg('re-using existing instance: gotoRaDec+setupCatalogs');
                            window._aladinInstance.gotoRaDec(ra, dec);
                            window._aladinInstance.setFov(fov);
                            window._aladinInstance.setImageSurvey(survey);
                            clearTimeout(window._setupCatalogsTimer);
                            window._setupCatalogsTimer = setTimeout(function() { setupCatalogs(window._aladinInstance); }, 50);
                        } else {
                            dbg('first init: waiting for #aladin-div to be sized');
                            // Wait for #aladin-div to be visible and sized before init
                            // (Aladin v3 reads canvas size at creation; div hidden = blank)
                            var attempts = 0;
                            function tryInit() {
                                var divEl = document.getElementById('aladin-div');
                                if (!divEl || divEl.offsetWidth === 0 || divEl.offsetHeight === 0) {
                                    if (attempts++ < 40) { setTimeout(tryInit, 50); }
                                    return;
                                }
                                var inst = A.aladin('#aladin-div', {
                                    target: ra + ' ' + dec,
                                    fov: fov,
                                    survey: survey,
                                    cooFrame: 'ICRSd',
                                    showReticle: false,
                                    showZoomControl: false,
                                    showLayersControl: true,
                                    showFrame: false,
                                    showGotoControl: false,
                                    showShareControl: false,
                                    showProjectionControl: false
                                });
                                window._aladinInstance = inst;

                                // Mask polygons are rendered via setupCatalogs from figure.data (no CDN needed)

                                // Click bridge
                                try {
                                    inst.on('objectsSelected', function(objs) {
                                        if (objs && objs.length > 0) {
                                            var o = objs[0];
                                            window._aladinPendingClick = {
                                                ra: o.ra, dec: o.dec,
                                                name: (o.data && o.data.name) ? o.data.name : '',
                                                timestamp: Date.now()
                                            };
                                        }
                                    });
                                } catch(e) {}

                                clearTimeout(window._setupCatalogsTimer);
                                window._setupCatalogsTimer = setTimeout(function() { setupCatalogs(inst); }, 50);
                            }
                            tryInit();
                        }
                    };

                    if (typeof A !== 'undefined' && A.init && typeof A.init.then === 'function') {
                        A.init.then(doInit).catch(function(e) { console.error('[Aladin] A.init failed:', e); });
                    } else if (typeof A !== 'undefined') {
                        doInit();
                    }
                }

                // Lazy-load Aladin Lite CSS + JS from CDN on first call
                if (!document.getElementById('aladin-css')) {
                    var link = document.createElement('link');
                    link.id = 'aladin-css'; link.rel = 'stylesheet';
                    link.href = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.css';
                    document.head.appendChild(link);
                }
                if (!document.getElementById('aladin-js')) {
                    var script = document.createElement('script');
                    script.id = 'aladin-js'; script.charset = 'utf-8';
                    script.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js';
                    script.onload = function() { doAladinInit(overlayData); };
                    document.head.appendChild(script);
                    return window.dash_clientside.no_update;
                }

                doAladinInit(overlayData);
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-init-dummy", "children"),
            [Input("aladin-overlay-data-store", "data"),
             Input("view-mode-store", "data")],
            prevent_initial_call=True,
        )

        # When Aladin survey dropdown changes, update the live instance survey
        self.app.clientside_callback(
            """
            function(survey) {
                if (survey && window._aladinInstance) {
                    window._aladinInstance.setImageSurvey(survey);
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-init-dummy", "children", allow_duplicate=True),
            Input("aladin-survey-dropdown", "value"),
            prevent_initial_call=True,
        )

        # Aladin click poll: dcc.Interval → aladin-click-store
        self.app.clientside_callback(
            """
            function(n) {
                if (window._aladinPendingClick) {
                    var data = window._aladinPendingClick;
                    window._aladinPendingClick = null;
                    return data;
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-click-store", "data"),
            Input("aladin-click-poll-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Pre-fetch Aladin CDN assets ~3s after page load, then pre-init hidden instance
        self.app.clientside_callback(
            """
            function(n) {
                function maybePreInit() {
                    if (window._aladinInstance) return;
                    var divEl = document.getElementById('aladin-div');
                    if (!divEl || divEl.offsetWidth === 0 || divEl.offsetHeight === 0) return;
                    try {
                        var doPreInit = function() {
                            if (window._aladinInstance) return;
                            var inst = A.aladin('#aladin-div', {
                                target: '180 0', fov: 1.0,
                                survey: 'P/DESI-Legacy-Surveys/DR10/color',
                                cooFrame: 'ICRSd',
                                showReticle: false, showZoomControl: false,
                                showLayersControl: true, showFrame: false,
                                showGotoControl: false, showShareControl: false,
                                showProjectionControl: false
                            });
                            window._aladinInstance = inst;
                        };
                        if (typeof A !== 'undefined' && A.init && typeof A.init.then === 'function') {
                            A.init.then(doPreInit).catch(function() {});
                        } else if (typeof A !== 'undefined') {
                            doPreInit();
                        }
                    } catch(e) {}
                }
                if (!document.getElementById('aladin-css')) {
                    var link = document.createElement('link');
                    link.id = 'aladin-css'; link.rel = 'stylesheet';
                    link.href = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.css';
                    document.head.appendChild(link);
                }
                if (!document.getElementById('aladin-js')) {
                    var script = document.createElement('script');
                    script.id = 'aladin-js'; script.charset = 'utf-8';
                    script.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js';
                    script.onload = function() { setTimeout(maybePreInit, 200); };
                    document.head.appendChild(script);
                } else {
                    maybePreInit();
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-init-dummy", "children", allow_duplicate=True),
            Input("aladin-preload-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Disable mosaic cutout button when in ESA Sky or Aladin mode
        self.app.clientside_callback(
            """
            function(mode) {
                const disabled = mode === 'aladin';
                return [disabled, disabled];
            }
            """,
            [Output("tab-cutout-button", "disabled"),
             Output("tab-generate-cutout", "disabled")],
            Input("view-mode-store", "data"),
        )

        # Handle richness filter mode switch (ZP vs RS) - show/hide appropriate filter
        self.app.clientside_callback(
            """
            function(selectedValue) {
                // Return appropriate styles to show/hide components based on selection
                if (selectedValue === 'zp') {
                    return [{display: 'block'}, {display: 'none'}, {display: 'none'}];
                } else if (selectedValue === 'rs') {
                    return [{display: 'none'}, {display: 'block'}, {display: 'none'}];
                } else {
                    // None selection
                    return [{display: 'none'}, {display: 'none'}, {display: 'block'}];
                }
            }
            """,
            [
                Output("richness-zp-container", "style"),
                Output("richness-rs-container", "style"),
                Output("richness-none-container", "style")
            ],
            Input("richness-mode-radio", "value"),
        )


    #     return 0