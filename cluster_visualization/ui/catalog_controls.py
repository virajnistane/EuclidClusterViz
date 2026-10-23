"""
Galaxy catalogs sidebar section and its Add/Edit dialog.

The section lists the user's catalogs (CatalogRegistry) with a Show switch each,
and holds the "CATRED near shown catalogs" controls. The dialog maps a catalog
file's columns to the app's standard roles (galaxy_catalog.ROLES). Callbacks:
callbacks/catalog_callbacks.py. Styling: ``catalog-*`` classes in enhanced_styles.css.
"""

import os

import dash_bootstrap_components as dbc
from dash import dcc, html

from cluster_visualization.src.data.galaxy_catalog import ROLES
from cluster_visualization.src.visualization.catalog_traces import SYMBOLS


def _badges(spec):
    mapped = set(spec.columns)
    badges = []
    for role, text, title in (
        ("OBJECT_ID", "ID", "OBJECT_ID mapped: exact CATRED match"),
        ("SPEC_Z", "spec-z", "Spectroscopic redshift mapped"),
        ("CLUSTER_ID", "clusters", "Cluster IDs mapped: usable in the cluster filter"),
    ):
        if role in mapped:
            badges.append(html.Span(text, className="catalog-badge", title=title))
    return badges


def _labelled_row(label, label_for, help_text, control):
    """Mapping line in the dialog: label and help on the left, the control on the right."""
    return dbc.Row(
        [
            dbc.Col(
                [
                    html.Label(label, htmlFor=label_for, className="catalog-role-label"),
                    html.Small(help_text, className="control-help"),
                ],
                width=5,
            ),
            dbc.Col(control, width=7),
        ],
        className="catalog-role-row align-items-center",
    )


class CatalogControls:
    """Galaxy catalogs section, catalog list rows and the Add/Edit dialog."""

    @staticmethod
    def create_section():
        return html.Div(
            [
                dcc.Store(id="catalog-registry-version", data=0),
                dcc.Store(id="catalog-window-store"),
                html.Div(id="catalog-list", className="catalog-list"),
                dbc.Button(
                    [html.I(className="fas fa-plus me-2"), "Add catalog"],
                    id="catalog-add-button",
                    color="secondary",
                    outline=True,
                    size="sm",
                    className="w-100 mt-2 mb-3",
                    n_clicks=0,
                ),
                html.Div(
                    [
                        html.Div("CATRED near shown catalogs", className="control-label"),
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("Match radius (arcsec)"),
                                dbc.Input(
                                    id="catalog-match-radius-arcsec",
                                    type="number",
                                    min=0.1,
                                    step=0.1,
                                    value=3.0,
                                ),
                            ],
                            size="sm",
                            className="mb-2",
                        ),
                        dbc.Button(
                            [
                                html.I(className="fas fa-crosshairs me-2"),
                                "Load CATRED near shown catalogs",
                            ],
                            id="catalog-match-button",
                            color="info",
                            size="sm",
                            className="w-100",
                            n_clicks=0,
                            disabled=True,
                        ),
                        html.Small(
                            "Zoom in to enable (view under 2° × 2°). Marks the CATRED sources of the shown "
                            "catalogs' galaxies: by OBJECT_ID when mapped (radius not used), else "
                            "within the radius. Click one for its p(z).",
                            className="control-help",
                        ),
                        html.Small(id="catalog-match-feedback", className="control-help"),
                    ],
                    className="control-group",
                ),
            ]
        )

    @staticmethod
    def catalog_rows(specs, shown=frozenset()):
        """One row per catalog: Show switch, colour, feature badges, Edit/Remove."""
        if not specs:
            return html.Small(
                "No catalogs yet. Add one from a FITS, CSV, ECSV or Parquet file on the cluster.",
                className="control-help",
            )
        return [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                className="catalog-swatch", style={"backgroundColor": spec.color}
                            ),
                            dbc.Switch(
                                id={"type": "catalog-show", "index": spec.id},
                                label=spec.name,
                                value=spec.id in shown,
                                className="catalog-show",
                            ),
                            html.Span(_badges(spec), className="catalog-badges"),
                            html.Button(
                                html.I(className="fas fa-pen"),
                                id={"type": "catalog-edit", "index": spec.id},
                                n_clicks=0,
                                type="button",
                                className="btn btn-sm btn-link catalog-action",
                                title=f"Edit {spec.name}",
                                **{"aria-label": f"Edit {spec.name}"},
                            ),
                            html.Button(
                                html.I(className="fas fa-trash"),
                                id={"type": "catalog-remove", "index": spec.id},
                                n_clicks=0,
                                type="button",
                                className="btn btn-sm btn-link catalog-action",
                                title=f"Remove {spec.name} from the list (the file is not touched)",
                                **{"aria-label": f"Remove {spec.name}"},
                            ),
                        ],
                        className="catalog-row-main",
                    ),
                    html.Small(
                        os.path.basename(spec.path),
                        id={"type": "catalog-status", "index": spec.id},
                        className="control-help catalog-status",
                        title=spec.path,
                    ),
                ],
                className="catalog-row",
            )
            for spec in specs
        ]

    @staticmethod
    def create_modal():
        symbol_options = [{"label": label, "value": value} for value, (label, _) in SYMBOLS.items()]
        role_rows = [
            _labelled_row(
                role.label + (" *" if role.required else ""),
                f"catalog-role-{role.name}",
                role.enables,
                dcc.Dropdown(
                    id=f"catalog-role-{role.name}",
                    options=[],
                    placeholder="Required" if role.required else "Not used",
                    clearable=not role.required,
                ),
            )
            for role in ROLES
        ]
        return dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Add galaxy catalog", id="catalog-modal-title")),
                dbc.ModalBody(
                    [
                        dcc.Store(id="catalog-modal-state"),
                        dcc.Store(id="catalog-table-store"),
                        html.Label(
                            "Catalog file on the cluster",
                            htmlFor="catalog-path-input",
                            className="control-label",
                        ),
                        dbc.InputGroup(
                            [
                                dbc.Input(
                                    id="catalog-path-input",
                                    placeholder="/sps/euclid/.../catalog.fits",
                                    type="text",
                                ),
                                dbc.Button(
                                    "Read columns",
                                    id="catalog-read-button",
                                    n_clicks=0,
                                    color="primary",
                                ),
                            ],
                            size="sm",
                        ),
                        html.Small(
                            "FITS, CSV, ECSV or Parquet. Only the column list is read here; the file "
                            "stays on the cluster.",
                            className="control-help",
                        ),
                        html.Div(id="catalog-path-feedback", className="mt-2"),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Label(
                                            "Table",
                                            htmlFor="catalog-hdu-dropdown",
                                            className="control-label",
                                        ),
                                        dcc.Dropdown(id="catalog-hdu-dropdown", clearable=False),
                                    ],
                                    id="catalog-hdu-row",
                                    style={"display": "none"},
                                    className="mb-3",
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Label(
                                                    "Name",
                                                    htmlFor="catalog-name-input",
                                                    className="control-label",
                                                ),
                                                dbc.Input(
                                                    id="catalog-name-input", type="text", size="sm"
                                                ),
                                            ],
                                            width=6,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label(
                                                    "Colour",
                                                    htmlFor="catalog-color-input",
                                                    className="control-label",
                                                ),
                                                dbc.Input(
                                                    id="catalog-color-input",
                                                    type="color",
                                                    value="#ff8800",
                                                    size="sm",
                                                ),
                                            ],
                                            width=2,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label(
                                                    "Marker",
                                                    htmlFor="catalog-symbol-dropdown",
                                                    className="control-label",
                                                ),
                                                dcc.Dropdown(
                                                    id="catalog-symbol-dropdown",
                                                    options=symbol_options,
                                                    value="diamond",
                                                    clearable=False,
                                                ),
                                            ],
                                            width=4,
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                html.Div("Columns", className="control-label"),
                                html.Small(
                                    "Map only what you need; each line says what a mapping turns on. "
                                    "Suggestions come from common column names.",
                                    className="control-help mb-2",
                                ),
                                html.Div(role_rows),
                                _labelled_row(
                                    "Keep only rows where",
                                    "catalog-select-dropdown",
                                    "a true/false column, e.g. a quality flag",
                                    dcc.Dropdown(
                                        id="catalog-select-dropdown", placeholder="All rows"
                                    ),
                                ),
                                _labelled_row(
                                    "Also show on hover",
                                    "catalog-hover-dropdown",
                                    "any other columns",
                                    dcc.Dropdown(id="catalog-hover-dropdown", multi=True),
                                ),
                                html.Div(id="catalog-check-feedback", className="mt-3"),
                            ],
                            id="catalog-mapping-section",
                            style={"display": "none"},
                            className="mt-3",
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Cancel",
                            id="catalog-cancel-button",
                            n_clicks=0,
                            color="secondary",
                            outline=True,
                        ),
                        dbc.Button(
                            "Check", id="catalog-check-button", n_clicks=0, color="secondary"
                        ),
                        dbc.Button("Save", id="catalog-save-button", n_clicks=0, color="primary"),
                    ]
                ),
            ],
            id="catalog-modal",
            is_open=False,
            size="lg",
            scrollable=True,
            backdrop="static",
        )
