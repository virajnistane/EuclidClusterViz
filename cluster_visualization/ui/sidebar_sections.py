"""
Sidebar control sections for the cluster visualization app.

Contains all sidebar control UI components: catalog selection, cluster
filters, display settings and application configuration. Styling lives in
enhanced_styles.css (``control-*``, ``range-*`` and ``apply-bar`` classes);
components here only carry structure.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


def _group_label(text, html_for=None):
    """Heading for one control group (a filter or a setting)."""
    if html_for:
        return html.Label(text, htmlFor=html_for, className="control-label")
    return html.Div(text, className="control-label")


def _help(children, help_id=None):
    """Muted one-line explanation under a control."""
    if help_id:
        return html.Small(html.Span(children, id=help_id), className="control-help")
    return html.Small(children, className="control-help")


def _pending_tag(control_id):
    """'Not applied' tag shown while a control differs from the last render (set clientside)."""
    return html.Span(
        "Not applied",
        id=f"{control_id}-pending",
        className="range-readout-flag pending-tag",
        style={"display": "none"},
    )


def _switch(switch_id, label, value, help_text=None, help_id=None, disabled=False):
    """Switch with optional help line, as one control group."""
    children = [dbc.Switch(id=switch_id, label=label, value=value, disabled=disabled)]
    if help_text is not None:
        children.append(_help(help_text, help_id))
    return html.Div(children, className="control-group")


def _range_inputs(slider_id):
    """Paired min/max number inputs kept in sync with a RangeSlider."""

    def bound_input(suffix, label):
        input_id = f"{slider_id}-{suffix}"
        return dbc.Col(
            [
                html.Label(label, htmlFor=input_id, className="range-input-label"),
                dbc.Input(
                    id=input_id,
                    type="number",
                    size="sm",
                    debounce=True,
                    className="range-input",
                ),
            ],
            width=6,
        )

    return dbc.Row([bound_input("lo", "Min"), bound_input("hi", "Max")], className="g-2 mb-2")


def _range_filter(slider_id, readout_id, missing_id, missing_label, missing_default,
                  default_max=100):
    """Readout + RangeSlider + min/max inputs + include-missing switch."""
    return html.Div(
        [
            # Selected-range readout (set clientside)
            html.Div(id=readout_id, className="range-readout"),
            dcc.RangeSlider(
                id=slider_id,
                min=0,
                max=default_max,
                step=0.1,
                marks={},
                value=[0, default_max],
                tooltip={"placement": "bottom", "always_visible": False},
                allowCross=False,
                className="custom-range-slider",
            ),
            _range_inputs(slider_id),
            dbc.Switch(id=missing_id, label=missing_label, value=missing_default),
            _pending_tag(missing_id),
        ]
    )


def _flag_checklist(checklist_id, estimate):
    """Quality-flag checklist for one richness estimate."""
    return html.Div(
        [
            html.Div(
                [f"Quality flag ({estimate})", _pending_tag(checklist_id)],
                className="control-sublabel d-flex align-items-center gap-2",
            ),
            dbc.Checklist(
                id=checklist_id,
                options=[
                    {"label": "0 · with richness", "value": 0},
                    {"label": "1 · dubious", "value": 1},
                    {"label": "2 · no richness", "value": 2},
                ],
                value=[0, 1, 2],
                inline=True,
                className="flag-checklist",
            ),
        ],
        className="mb-2",
    )


class SidebarSections:
    """Handles sidebar control sections"""

    # ------------------------------------------------------------------ Catalog

    @staticmethod
    def create_algorithm_section():
        """Detection algorithm selector"""
        return html.Div(
            [
                _group_label("Detection algorithm", "algorithm-dropdown"),
                dcc.Dropdown(
                    id="algorithm-dropdown",
                    options=[
                        {"label": "PZWAV", "value": "PZWAV"},
                        {"label": "AMICO", "value": "AMICO"},
                        {"label": "PZWAV and AMICO", "value": "BOTH"},
                    ],
                    value="PZWAV",
                    clearable=False,
                ),
            ],
            className="control-group",
        )

    @staticmethod
    def create_merged_clusters_section():
        """CL-tile information and unmerged-cluster toggles"""
        return html.Div(
            [
                _switch(
                    "cltile-info-switch",
                    "Show CL-tile information",
                    True,
                    "Color clusters by tile; show CL-tile polygons",
                    "cltile-info-switch-help-text",
                ),
                _switch(
                    "unmerged-clusters-switch",
                    "Show unmerged clusters",
                    False,
                    "Clusters in individual tiles but absent from merged catalog",
                    "unmerged-clusters-switch-help-text",
                ),
            ]
        )

    # ------------------------------------------------------------------ Filters

    @staticmethod
    def create_redshift_section():
        """Redshift range filter"""
        return html.Div(
            [
                _group_label("Redshift (z)", "redshift-range-slider"),
                _range_filter(
                    "redshift-range-slider",
                    "redshift-range-display",
                    "redshift-include-missing",
                    "Include clusters with missing redshift",
                    True,
                    default_max=10,
                ),
            ],
            className="control-group",
        )

    @staticmethod
    def create_snr_section():
        """SNR range filters; only the selected algorithm's filter is shown"""
        return html.Div(
            [
                _group_label("Signal-to-noise (SNR)"),
                html.Div(
                    [
                        html.Div("PZWAV", className="control-sublabel"),
                        _range_filter(
                            "snr-range-slider-pzwav",
                            "snr-range-display-pzwav",
                            "snr-include-missing-pzwav",
                            "Include clusters with missing SNR",
                            True,
                        ),
                    ],
                    id="snr-pzwav-container",
                    className="filter-variant",
                ),
                html.Div(
                    [
                        html.Div("AMICO", className="control-sublabel"),
                        _range_filter(
                            "snr-range-slider-amico",
                            "snr-range-display-amico",
                            "snr-include-missing-amico",
                            "Include clusters with missing SNR",
                            True,
                        ),
                    ],
                    id="snr-amico-container",
                    className="filter-variant",
                    style={"display": "none"},  # Algorithm defaults to PZWAV
                ),
            ],
            className="control-group",
        )

    @staticmethod
    def create_richness_section():
        """Richness filter on the ZP or RS estimate, or off"""
        return html.Div(
            [
                _group_label("Richness", "richness-mode-radio"),
                dbc.RadioItems(
                    id="richness-mode-radio",
                    options=[
                        {"label": "Off", "value": "none"},
                        {"label": "ZP", "value": "zp"},
                        {"label": "RS", "value": "rs"},
                    ],
                    value="none",
                    inline=True,
                    className="mb-1",
                ),
                _pending_tag("richness-mode-radio"),
                _help("Richness from Rich-CL, the richness and membership code: ZP is its photometric-redshift branch, RS its red-sequence branch."),
                # Visibility of the three containers follows the radio value
                html.Div(
                    [
                        _flag_checklist("flag-quality-zp-checklist", "ZP"),
                        _range_filter(
                            "richness-range-slider-zp",
                            "richness-range-display-zp",
                            "richness-include-missing-zp",
                            "Include clusters with missing richness (ZP)",
                            False,
                        ),
                    ],
                    id="richness-zp-container",
                    className="filter-variant",
                    style={"display": "none"},
                ),
                html.Div(
                    [
                        _flag_checklist("flag-quality-rs-checklist", "RS"),
                        _range_filter(
                            "richness-range-slider-rs",
                            "richness-range-display-rs",
                            "richness-include-missing-rs",
                            "Include clusters with missing richness (RS)",
                            False,
                        ),
                    ],
                    id="richness-rs-container",
                    className="filter-variant",
                    style={"display": "none"},
                ),
                html.Div(
                    _help("No richness filter applied."),
                    id="richness-none-container",
                    style={"display": "block"},
                ),
            ],
            className="control-group",
        )

    @staticmethod
    def create_idcluster_section():
        """Restrict the plot to clusters listed in an uploaded ID file"""
        return html.Div(
            [
                _group_label("Cluster-ID list", "idcluster-upload"),
                dcc.Upload(
                    id="idcluster-upload",
                    children=html.Div(
                        [html.I(className="fas fa-upload me-2"), "Choose or drop a file"]
                    ),
                    accept=".txt,.csv,.dat",
                    className="id-upload",
                    multiple=False,
                ),
                html.Div(
                    [
                        html.Small(
                            "No ID list uploaded",
                            id="idcluster-status-display",
                            className="control-help mb-0",
                        ),
                        _pending_tag("idcluster-upload"),
                        dbc.Button(
                            "Clear",
                            id="idcluster-clear-button",
                            color="link",
                            size="sm",
                            className="p-0 ms-2",
                            style={"display": "none"},
                        ),
                    ],
                    className="d-flex align-items-baseline justify-content-between",
                ),
                _help(".txt, .csv or .dat, one ID per line"),
            ],
            className="control-group",
        )

    @staticmethod
    def create_cluster_matching_section():
        """Matched-cluster ovals, drawn for the zoom window at the next Apply"""
        return html.Div(
            [
                _group_label("Matched clusters"),
                dbc.Switch(
                    id="matching-clusters-switch",
                    label="Show matched clusters (CAT-CL)",
                    value=False,
                    disabled=True,
                ),
                _pending_tag("matching-clusters-switch"),
                html.Small(
                    "Zoom in, then press Apply filters",
                    id="viewport-zoom-indicator",
                    className="control-help",
                ),
            ],
            className="control-group",
        )

    @staticmethod
    def create_ned_specz_filter_section():
        """Only clusters with a NED spec-z cross-match (spec-z verification), at the next Apply"""
        return html.Div(
            [
                _group_label("Spec-z verification"),
                dbc.Switch(
                    id="ned-specz-filter-switch",
                    label="Only clusters with a NED spec-z match",
                    value=False,
                ),
                _pending_tag("ned-specz-filter-switch"),
                _help("Needs the NED catalog ([paths] ned_specz_fits in config.ini)"),
            ],
            className="control-group",
        )

    @staticmethod
    def create_apply_filters_bar():
        """Sticky bar with the single Apply action for every filter above"""
        return html.Div(
            [
                dbc.Button(
                    [html.I(className="fas fa-filter me-2"), "Apply filters"],
                    id="apply-filters-button",
                    color="secondary",
                    outline=True,
                    className="w-100 btn-enhanced",
                    n_clicks=0,
                    disabled=True,
                ),
                html.Small(
                    "Render once to enable filters",
                    id="apply-filters-status",
                    className="apply-bar-status",
                    **{"aria-live": "polite"},
                ),
            ],
            className="apply-bar",
        )

    # ------------------------------------------------------------------ Display

    @staticmethod
    def create_display_options_section():
        """Plot display toggles (update live)"""
        return html.Div(
            [
                _switch(
                    "mer-switch",
                    "Show MER tiles",
                    False,
                    "Up to LEV2 within CL-tiles; needs CL-tile polygons shown",
                ),
                _switch("polygon-switch", "Fill CL-tile (CORE) polygons", False),
                _switch(
                    "aspect-ratio-switch",
                    "Free aspect ratio",
                    True,
                    "Turn off to keep true sky proportions",
                ),
            ]
        )

    # ------------------------------------------------------------ Configuration

    @staticmethod
    def create_config_info_section():
        """Loaded catalog files and the GlueMatchCat file selector"""

        def loading():
            return html.Div(
                [dbc.Spinner(size="sm", color="secondary"), html.Span("Loading…", className="ms-2")]
            )

        return html.Div(
            [
                html.Div(
                    [
                        _group_label("Merged catalog"),
                        html.Div(id="config-merged-catalog", className="small", children=[loading()]),
                    ],
                    className="control-group",
                ),
                html.Div(
                    [
                        _group_label("Tile detection list"),
                        html.Div(id="config-detintile-list", className="small", children=[loading()]),
                    ],
                    className="control-group",
                ),
                html.Div(
                    [
                        _group_label("Current GlueMatchCat XML file", "gluematchcat-file-display"),
                        dbc.InputGroup(
                            [
                                dbc.Input(
                                    id="gluematchcat-file-display",
                                    type="text",
                                    value="No file selected",
                                    readonly=True,
                                ),
                                dbc.Button(
                                    [html.I(className="fas fa-folder-open me-1"), "Browse"],
                                    id="browse-file-button",
                                    color="secondary",
                                    outline=True,
                                    title="Browse for file",
                                ),
                            ],
                            size="sm",
                        ),
                    ],
                    className="control-group",
                ),
                html.Div(
                    [
                        _group_label("New file path", "gluematchcat-file-input"),
                        dbc.Input(
                            id="gluematchcat-file-input",
                            type="text",
                            size="sm",
                            placeholder="/path/to/gluematchcat_PZWAV_AMICO.xml",
                        ),
                    ],
                    id="gluematchcat-file-container",
                    className="control-group",
                ),
                dbc.Button(
                    [html.I(className="fas fa-check me-2"), "Use this file"],
                    id="apply-file-config-button",
                    color="secondary",
                    outline=True,
                    size="sm",
                    className="w-100 btn-enhanced",
                    disabled=True,
                ),
                html.Div(id="file-config-status", className="mt-2 small"),
            ]
        )
