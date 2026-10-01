"""
Tab content sections for cluster visualization app.

Cluster Tools tab: what you can do with the cluster selected on the map.

- A pinned summary of the selected cluster (with Deselect).
- Overlays: cutout, Healpix mask cutout, CATRED box and cluster members. Each
  trigger opens its options directly underneath it; only one is open at a time.
- Classify: a quick-tag bar (Good / Bad / Dubious, keys G / B / D) plus the full
  tagging panel with dataset label and CSV export.

Styling comes from enhanced_styles.css (``tool-*`` classes inside ``.cv-panel``).
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

# Default member marker colour: an orange that stays visible on dark cutouts and
# on the white plot background
MEMBERS_MARKER_DEFAULT = "#f76707"


def _pending(control_id):
    """'Not applied' tag shown while a member filter differs from the shown members."""
    return html.Span(
        "Not applied",
        id=f"{control_id}-pending",
        className="range-readout-flag pending-tag",
        style={"display": "none"},
    )


def _label(text, control_id):
    return html.Label(text, htmlFor=control_id, className="form-label tool-label")


def _field(text, control, control_id, width=6, help_text=None):
    children = [_label(text, control_id), control]
    if help_text:
        children.append(html.Small(help_text, className="control-help"))
    return dbc.Col(children, xs=12, sm=width)


def _number(control_id, value, min_value, max_value, step):
    return dbc.Input(
        id=control_id, type="number", value=value, min=min_value, max=max_value, step=step, size="sm"
    )


def _colour(control_id, value, name):
    return html.Div(
        dbc.Input(id=control_id, type="color", value=value, className="tool-colour"),
        title=name,
    )


def _overlay_actions(primary_id, primary_label, toggle_id, clear_id, primary_icon="fa-play"):
    """Generate (filled) · Hide (outline) · Clear (outline danger)."""
    idle = "Available once something has been generated"
    return html.Div(
        [
            dbc.Button(
                [html.I(className=f"fas {primary_icon} me-2", **{"aria-hidden": "true"}), primary_label],
                id=primary_id, color="primary", size="sm", n_clicks=0, className="tool-primary",
            ),
            dbc.Button(
                [html.I(className="fas fa-eye me-1", **{"aria-hidden": "true"}), "Hide"],
                id=toggle_id, color="secondary", outline=True, size="sm", n_clicks=0, disabled=True,
                title=idle,
            ),
            dbc.Button(
                [html.I(className="fas fa-trash me-1", **{"aria-hidden": "true"}), "Clear"],
                id=clear_id, color="danger", outline=True, size="sm", n_clicks=0, disabled=True,
                title=idle,
            ),
        ],
        className="tool-actions",
    )


def _tool(trigger_id, icon, title, collapse_id, body):
    """Disclosure row: trigger button with its options panel directly below."""
    return html.Div(
        [
            dbc.Button(
                [
                    html.I(className=f"fas {icon} tool-icon", **{"aria-hidden": "true"}),
                    html.Span(title, className="tool-title"),
                    html.I(className="fas fa-chevron-down tool-chevron", **{"aria-hidden": "true"}),
                ],
                id=trigger_id, color="link", n_clicks=0, className="tool-trigger",
            ),
            dbc.Collapse(html.Div(body, className="tool-panel"), id=collapse_id, is_open=False),
        ],
        className="tool-row",
    )


class TabContent:
    """Handles tab content sections"""

    @staticmethod
    def create_cluster_analysis_tab_content():
        """Create cluster analysis tab content for the tabbed interface"""
        cutout_panel = [
            dbc.Row(
                [
                    _field("Size (arcmin)", _number("tab-cutout-size", 2.0, 0.5, 20.0, 0.5), "tab-cutout-size"),
                    _field("Opacity (0–1)", _number("tab-cutout-opacity", 1.0, 0.0, 1.0, 0.1), "tab-cutout-opacity"),
                ],
                className="g-2",
            ),
            dbc.Row(
                [
                    _field(
                        "Colour scale",
                        dbc.Select(
                            id="tab-cutout-colorscale",
                            options=[{"label": c, "value": c} for c in ("viridis", "gray", "plasma")],
                            value="viridis",
                            size="sm",
                        ),
                        "tab-cutout-colorscale",
                    ),
                    dbc.Col(
                        [
                            html.Div("Source", className="form-label tool-label"),
                            html.Div("MER mosaic", className="tool-static"),
                            # Only one cutout source exists; kept for the callbacks that read it
                            dbc.Select(
                                id="tab-cutout-type",
                                options=[{"label": "MER Mosaic", "value": "mermosaic"}],
                                value="mermosaic",
                                style={"display": "none"},
                            ),
                        ],
                        xs=12, sm=6,
                    ),
                ],
                className="g-2",
            ),
            _overlay_actions("tab-generate-cutout", "Generate cutout", "tab-cutout-toggle-visibility", "tab-cutout-clear"),
        ]

        mask_panel = [
            dbc.Row(
                [
                    _field("Size (arcmin)", _number("tab-mask-cutout-size", 2.0, 0.5, 20.0, 0.5), "tab-mask-cutout-size"),
                    _field("Opacity (0–1)", _number("tab-mask-cutout-opacity", 0.3, 0.0, 1.0, 0.1), "tab-mask-cutout-opacity"),
                ],
                className="g-2",
            ),
            _overlay_actions(
                "tab-generate-mask-cutout", "Generate mask cutout",
                "tab-mask-cutout-toggle-visibility", "tab-mask-cutout-clear",
            ),
        ]

        catred_panel = [
            dbc.Row(
                [
                    _field("Box size (arcmin)", _number("tab-catred-box-size", 2.0, 1.0, 10.0, 1.0), "tab-catred-box-size"),
                    _field(
                        "Redshift bin width",
                        _number("tab-catred-redshift-bin-width", 0.5, 0.01, 3.0, 0.01),
                        "tab-catred-redshift-bin-width",
                    ),
                ],
                className="g-2",
            ),
            dbc.Row(
                [
                    _field(
                        "Coverage threshold (0–1)",
                        _number("tab-catred-mask-threshold", 0.8, 0.0, 1.0, 0.1),
                        "tab-catred-mask-threshold",
                    ),
                    _field(
                        "Magnitude limit (H)",
                        _number("tab-catred-maglim", 24.0, 20.0, 32.0, 1.0),
                        "tab-catred-maglim",
                    ),
                ],
                className="g-2",
            ),
            html.Small(
                "Threshold and magnitude limit are shared with the Mask section in the sidebar.",
                className="control-help mb-2",
            ),
            dbc.Row(
                [
                    _field(
                        "Marker size",
                        dbc.Select(
                            id="tab-catred-marker-size",
                            options=[
                                {"label": "Constant", "value": "set_size_custom"},
                                {"label": "KRON radius", "value": "set_size_kronradius"},
                            ],
                            value="set_size_custom",
                            size="sm",
                        ),
                        "tab-catred-marker-size",
                        width=4,
                    ),
                    _field(
                        "Constant size",
                        _number("tab-catred-marker-size-custom", 10.0, 5.0, 50.0, 5.0),
                        "tab-catred-marker-size-custom",
                        width=4,
                    ),
                    _field(
                        "Marker colour",
                        _colour("tab-catred-marker-color-picker", "#00FFF2", "CATRED marker colour"),
                        "tab-catred-marker-color-picker",
                        width=4,
                    ),
                ],
                className="g-2 tool-row-3",
            ),
            _overlay_actions(
                "tab-view-catred-box", "Load CATRED box",
                "tab-catred-box-toggle-visibility", "tab-catred-box-clear",
            ),
        ]

        members_panel = [
            html.Div(id="tab-cluster-members-output", className="mb-2"),
            dbc.Row(
                [
                    _field("Marker size", _number("tab-members-marker-size", 10.0, 4.0, 30.0, 1.0), "tab-members-marker-size"),
                    _field(
                        "Marker colour",
                        _colour("tab-members-marker-color-picker", MEMBERS_MARKER_DEFAULT, "Members marker colour"),
                        "tab-members-marker-color-picker",
                    ),
                ],
                className="g-2",
            ),
            _overlay_actions(
                "tab-view-cluster-members", "Show members",
                "tab-members-toggle-visibility", "tab-members-clear",
            ),
            html.Div("Filter members", className="tool-subheading"),
            html.Small(
                "Filters from Rich-CL, the richness and membership code. ZP is its photometric-redshift "
                "branch, RS its red-sequence branch.",
                className="control-help mb-2",
            ),
            html.Div(
                [_label("Membership probability (PMEM)", "tab-members-filter-mode"), _pending("tab-members-filter-mode")],
                className="d-flex align-items-center gap-2",
            ),
            dbc.RadioItems(
                id="tab-members-filter-mode",
                options=[
                    {"label": "Off", "value": "none"},
                    {"label": "ZP", "value": "zp"},
                    {"label": "RS", "value": "rs"},
                ],
                value="none",
                inline=True,
                className="mb-1",
            ),
            dbc.Collapse(
                html.Div(
                    [
                        html.Div(
                            [_label("Keep members with PMEM above", "tab-members-pmem-slider"), _pending("tab-members-pmem-slider")],
                            className="d-flex align-items-center gap-2",
                        ),
                        dcc.Slider(
                            id="tab-members-pmem-slider",
                            min=0.0, max=1.0, step=0.05, value=0.5, marks=None,
                            tooltip={"placement": "bottom", "always_visible": True},
                            className="custom-slider",
                        ),
                    ]
                ),
                id="tab-members-pmem-slider-collapse",
                is_open=False,
            ),
            dbc.Switch(
                id="tab-members-mag-filter-switch",
                label="Magnitude limit (H★ band)",
                value=True,
                className="mb-0",
            ),
            _pending("tab-members-mag-filter-switch"),
            html.Div(
                [_label("Radius (ZP or RS branch)", "tab-members-radius-filter-mode"), _pending("tab-members-radius-filter-mode")],
                className="d-flex align-items-center gap-2 mt-2",
            ),
            dbc.RadioItems(
                id="tab-members-radius-filter-mode",
                options=[
                    {"label": "Off", "value": "none"},
                    {"label": "ZP", "value": "zp"},
                    {"label": "RS", "value": "rs"},
                ],
                value="none",
                inline=True,
                className="mb-2",
            ),
            dbc.Button(
                [html.I(className="fas fa-filter me-2", **{"aria-hidden": "true"}), "Apply member filters"],
                id="tab-members-apply-filter",
                color="secondary",
                outline=True,
                size="sm",
                className="w-100",
                n_clicks=0,
                disabled=True,
                title="Available once members are shown",
            ),
        ]

        quick_tag_bar = html.Div(
            [
                html.Div(
                    [
                        dbc.Button(
                            [label, html.Kbd(key, className="tool-kbd")],
                            id=f"tab-quick-tag-{value}",
                            color="secondary",
                            outline=True,
                            size="sm",
                            n_clicks=0,
                            className=f"quick-tag quick-tag-{value}",
                            title=f"Tag as {label.lower()} (key {key}); press again to remove",
                        )
                        for label, value, key in (("Good", "good", "G"), ("Bad", "bad", "B"), ("Dubious", "dubious", "D"))
                    ],
                    className="quick-tag-bar",
                    role="group",
                    **{"aria-label": "Tag the selected cluster"},
                ),
                html.Div(
                    id="tag-quick-status",
                    className="control-help",
                    role="status",
                    **{"aria-live": "polite"},
                ),
            ]
        )

        tagging_panel = [
            html.Div(
                id="tag-panel-cluster-preview",
                className="tool-preview",
                children=html.Small("No cluster selected.", className="text-muted"),
            ),
            dbc.Row(
                [
                    _field(
                        "Tag",
                        dbc.Select(
                            id="tab-tag-value",
                            options=[
                                {"label": "None", "value": "none"},
                                {"label": "Good", "value": "good"},
                                {"label": "Bad", "value": "bad"},
                                {"label": "Dubious", "value": "dubious"},
                            ],
                            value="none",
                            size="sm",
                        ),
                        "tab-tag-value",
                        width=4,
                    ),
                    _field(
                        "Dataset label",
                        dbc.Input(
                            id="tab-tag-dataset-label",
                            type="text",
                            size="sm",
                            placeholder="Optional, e.g. run1 (saved lowercase)",
                        ),
                        "tab-tag-dataset-label",
                        width=8,
                    ),
                ],
                className="g-2",
            ),
            dbc.Row(
                _field(
                    "CSV output path",
                    dbc.Input(
                        id="tagged-clusters-output-path",
                        type="text",
                        size="sm",
                        placeholder="/path/to/tagged_clusters.csv",
                        persistence=True,
                        persistence_type="local",
                    ),
                    "tagged-clusters-output-path",
                    width=12,
                    help_text="The file is written on the server running ClusterViz (the cluster, next to the "
                    "data), not on the computer where this browser runs. The path is remembered in this browser.",
                ),
                className="g-2",
            ),
            html.Div(
                [
                    dbc.Button(
                        [html.I(className="fas fa-tag me-2", **{"aria-hidden": "true"}), "Add / update tag"],
                        id="tab-tag-button",
                        color="primary",
                        size="sm",
                        n_clicks=0,
                        title="Saves the chosen tag; None removes the cluster's tag",
                        className="tool-primary",
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-save me-2", **{"aria-hidden": "true"}), "Save tagged CSV"],
                        id="tab-save-tagged-clusters-button",
                        color="secondary",
                        outline=True,
                        size="sm",
                        n_clicks=0,
                    ),
                ],
                className="tool-actions",
            ),
            html.Small(
                "Tags are kept for this session and saved with a tag column right after ID_UNIQUE_CLUSTER.",
                className="control-help mb-2",
            ),
            html.Div(
                id="tagged-clusters-summary",
                children=[html.Small("No tagged clusters yet.", className="text-muted")],
            ),
        ]

        return html.Div(
            [
                # No cluster selected
                html.Div(
                    [
                        html.I(className="fas fa-crosshairs tool-empty-icon", **{"aria-hidden": "true"}),
                        html.Div("No cluster selected", className="tool-empty-title"),
                        html.P(
                            "Click a cluster on the map to make cutouts, load its CATRED box or "
                            "members, and tag it.",
                            className="tool-empty-text",
                        ),
                    ],
                    id="cluster-no-selection",
                    className="tool-empty",
                ),
                # Cluster selected
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Selected cluster", className="tool-summary-title"),
                                        dbc.Button(
                                            "Deselect",
                                            id="cluster-deselect-button",
                                            color="link",
                                            size="sm",
                                            n_clicks=0,
                                            className="p-0",
                                        ),
                                    ],
                                    className="d-flex justify-content-between align-items-baseline",
                                ),
                                html.Div(id="cluster-info-display-tab"),
                            ],
                            className="tool-summary",
                        ),
                        html.Div("Overlays", className="tool-group-title"),
                        _tool("tab-cutout-button", "fa-crop", "Image cutout", "tab-cutout-options", cutout_panel),
                        _tool(
                            "tab-mask-cutout-button", "fa-layer-group", "Healpix mask cutout",
                            "tab-mask-cutout-options", mask_panel,
                        ),
                        _tool(
                            "tab-catred-box-button", "fa-magnifying-glass", "CATRED box",
                            "tab-catred-box-options", catred_panel,
                        ),
                        _tool(
                            "tab-cluster-members-button", "fa-users", "Cluster members",
                            "tab-cluster-members-options", members_panel,
                        ),
                        html.Div("Classify", className="tool-group-title"),
                        quick_tag_bar,
                        _tool("tab-tag-panel-button", "fa-tags", "Tagging and export", "tab-tagging-options", tagging_panel),
                        # Progress of the current action
                        html.Div(
                            [
                                dbc.Progress(id="tab-action-progress", value=0, striped=True, animated=True, className="mb-1"),
                                html.Span("", id="tab-action-label", className="control-help"),
                            ],
                            id="tab-action-progress-container",
                            style={"display": "none"},
                            className="mb-2",
                        ),
                        html.Div("Activity", className="tool-group-title"),
                        html.Div(
                            id="cluster-analysis-results",
                            children=[html.Small("Results of your actions appear here.", className="text-muted")],
                            className="tool-activity",
                        ),
                        dbc.Modal(
                            [
                                dbc.ModalHeader(dbc.ModalTitle("Tagged CSV already exists")),
                                dbc.ModalBody(
                                    [
                                        html.P("That file already exists. How should the tagged clusters be saved?"),
                                        html.Div(id="tagged-clusters-save-conflict-message"),
                                    ]
                                ),
                                dbc.ModalFooter(
                                    [
                                        dbc.Button("Cancel", id="tagged-clusters-cancel-save-button", color="secondary", outline=True, n_clicks=0),
                                        dbc.Button("Overwrite", id="tagged-clusters-overwrite-button", color="danger", outline=True, n_clicks=0),
                                        dbc.Button("Save with suffix", id="tagged-clusters-save-suffix-button", color="secondary", outline=True, n_clicks=0),
                                        dbc.Button("Append", id="tagged-clusters-append-button", color="primary", n_clicks=0),
                                    ]
                                ),
                            ],
                            id="tagged-clusters-save-conflict-modal",
                            is_open=False,
                            centered=True,
                        ),
                        dcc.Store(id="selected-cluster-merged-record", data=None),
                        dcc.Store(id="tagged-clusters-store", data=[]),
                        dcc.Store(id="tagged-clusters-pending-save", data=None),
                        dcc.Store(id="selected-cluster-box-coords", data=None),
                        # Member filter values used for the members currently drawn
                        dcc.Store(id="members-applied-filters", data=None),
                        html.Div(id="quick-tag-keys", style={"display": "none"}),
                    ],
                    id="cluster-selected-content",
                    style={"display": "none"},
                ),
            ],
            className="cluster-tools",
        )
