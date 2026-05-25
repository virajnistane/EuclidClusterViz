"""
Data control sections for CATRED and mosaic functionality.

Contains UI components for CATRED data filtering and mosaic/healpix mask controls.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


class DataControls:
    """Handles data control sections for CATRED and mosaic"""

    @staticmethod
    def create_catred_data_section():
        """Create High-res CATRED data section with enhanced styling"""
        return html.Div(
            [
                # Main CATRED toggle with beautiful styling
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-microscope me-0 text-warning"),
                                        dbc.Switch(
                                            id="catred-mode-switch",
                                            label="Hide sources under Healpix Mask",
                                            value=True,
                                            className="ms-1",
                                        ),
                                    ],
                                    className="d-flex align-items-center mb-0",
                                ),
                                dbc.Badge(
                                    [html.I(className="fas fa-zoom-in me-1"), "When zoomed < 2°"],
                                    color="warning",
                                    className="opacity-75",
                                ),
                            ]
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #fff3cd, #ffffff)",
                        "border-radius": "12px",
                    },
                ),
                # Threshold controls in beautiful card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-sliders-h me-0"),
                                        html.H6("Coverage Threshold", className="mb-0"),
                                    ],
                                    className="d-flex align-items-center",
                                )
                            ],
                            className="border-0",
                            style={
                                "background": "linear-gradient(45deg, #ffeaa7, #fdcb6e)",
                                "border-radius": "8px 8px 0 0",
                            },
                        ),
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        dcc.Slider(
                                            id="catred-threshold-slider",
                                            min=0.0,
                                            max=1.0,
                                            step=0.01,
                                            value=0.8,
                                            marks={
                                                0.0: {
                                                    "label": "0.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                0.2: {
                                                    "label": "0.2",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                0.4: {
                                                    "label": "0.4",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                0.6: {
                                                    "label": "0.6",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                0.8: {
                                                    "label": "0.8",
                                                    "style": {
                                                        "color": "#e17055",
                                                        "font-weight": "bold",
                                                        "fontSize": "13px",
                                                    },
                                                },
                                                1.0: {
                                                    "label": "1.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                            },
                                            tooltip={
                                                "placement": "bottom",
                                                "always_visible": False,
                                                "style": {"fontSize": "12px"},
                                            },
                                            className="custom-slider",
                                        )
                                    ],
                                    id="catred-threshold-container",
                                    className="mb-0",
                                    style={
                                        "padding": "10px 15px",
                                        "margin": "5px 0",
                                        "minHeight": "60px",
                                    },
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-info-circle me-1"),
                                        "For masked CATRED filtering",
                                    ],
                                    className="text-muted",
                                ),
                            ]
                        ),
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={"border-radius": "12px"},
                ),
                # Magnitude controls in beautiful card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-star me-2"),
                                        html.H6("Magnitude Limit (H-band)", className="mb-0"),
                                    ],
                                    className="d-flex align-items-center",
                                )
                            ],
                            className="border-0",
                            style={
                                "background": "linear-gradient(45deg, #a29bfe, #6c5ce7)",
                                "color": "white",
                                "border-radius": "8px 8px 0 0",
                            },
                        ),
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        dcc.Slider(
                                            id="magnitude-limit-slider",
                                            min=20.0,
                                            max=32.0,
                                            step=0.1,
                                            value=24.0,
                                            marks={
                                                20.0: {
                                                    "label": "20.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                22.0: {
                                                    "label": "22.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                24.0: {
                                                    "label": "24.0",
                                                    "style": {
                                                        "color": "#6c5ce7",
                                                        "font-weight": "bold",
                                                        "fontSize": "13px",
                                                    },
                                                },
                                                26.0: {
                                                    "label": "26.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                28.0: {
                                                    "label": "28.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                30.0: {
                                                    "label": "30.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                32.0: {
                                                    "label": "32.0",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                            },
                                            tooltip={
                                                "placement": "bottom",
                                                "always_visible": False,
                                                "style": {"fontSize": "12px"},
                                            },
                                            className="custom-slider",
                                        )
                                    ],
                                    id="magnitude-limit-container",
                                    className="mb-0",
                                    style={
                                        "padding": "10px 15px",
                                        "margin": "5px 0",
                                        "minHeight": "60px",
                                    },
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-info-circle me-1"),
                                        "Keep sources brighter than limit",
                                    ],
                                    className="text-muted",
                                ),
                            ]
                        ),
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={"border-radius": "12px"},
                ),
                # CATRED Data Controls with enhanced styling
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-tools me-0"),
                                        html.H6("CATRED Data Controls", className="mb-0"),
                                    ],
                                    className="d-flex align-items-center",
                                )
                            ],
                            className="border-0",
                            style={
                                "background": "linear-gradient(45deg, #74b9ff, #0984e3)",
                                "color": "white",
                                "border-radius": "8px 8px 0 0",
                            },
                        ),
                        dbc.CardBody(
                            [
                                # Render button
                                dbc.Button(
                                    [html.I(className="fas fa-eye me-2"), "🔍 Render CATRED Data"],
                                    id="catred-render-button",
                                    color="info",
                                    size="sm",
                                    className="w-100 mb-0 shadow-sm btn-enhanced",
                                    n_clicks=0,
                                    disabled=True,
                                    style={"border-radius": "8px", "font-weight": "600"},
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-search-plus me-0"),
                                        "Zoom in first, then click",
                                    ],
                                    className="text-muted d-block text-left mb-2",
                                ),
                                # Marker color picker
                                html.Div(
                                    [
                                        html.Label(
                                            "Marker color",
                                            className="form-label small text-muted mb-1",
                                            style={"font-size": "0.8rem"},
                                        ),
                                        dbc.Input(
                                            id="catred-render-marker-color",
                                            type="color",
                                            value="#000000",
                                            className="w-100",
                                            style={
                                                "height": "28px",
                                                "cursor": "pointer",
                                                "border-radius": "6px",
                                                "padding": "1px 2px",
                                            },
                                        ),
                                    ],
                                    className="mb-2",
                                ),
                                # CATRED visibility and delete controls
                                html.Div(
                                    [
                                        dbc.Button(
                                            [html.I(className="fas fa-eye me-1"), "Hide"],
                                            id="catred-toggle-visibility-button",
                                            color="secondary",
                                            size="sm",
                                            outline=True,
                                            className="me-1",
                                            n_clicks=0,
                                            disabled=True,
                                            style={"border-radius": "6px", "font-size": "0.85rem"},
                                        ),
                                        dbc.Button(
                                            [html.I(className="fas fa-trash-alt me-1"), "Clear"],
                                            id="catred-clear-button",
                                            color="danger",
                                            size="sm",
                                            outline=True,
                                            n_clicks=0,
                                            disabled=True,
                                            style={"border-radius": "6px", "font-size": "0.85rem"},
                                        ),
                                    ],
                                    className="d-flex justify-content-between",
                                ),
                            ],
                            className="p-3",
                        ),
                    ],
                    id="catred-controls-container",
                    className="border-0 shadow-sm",
                    style={"border-radius": "12px"},
                ),
            ]
        )

    @staticmethod
    def create_mosaic_controls_section():
        """Create mosaic image controls section with enhanced styling"""
        return html.Div(
            [
                # Main mosaic toggle
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-images me-0 text-info"),
                                        dbc.Switch(
                                            id="mosaic-enable-switch",
                                            label="Enable mosaic images",
                                            value=True,
                                            disabled=False,
                                            className="ms-1",
                                        ),
                                    ],
                                    className="d-flex align-items-left mb-0",
                                ),
                            ]
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #e8f4f8, #ffffff)",
                        "border-radius": "10px",
                    },
                ),
                # Opacity control
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-adjust me-2"),
                                        html.H6("Mosaic Opacity", className="mb-0"),
                                    ],
                                    className="d-flex align-items-center",
                                )
                            ],
                            className="border-0",
                            style={
                                "background": "linear-gradient(45deg, #74b9ff, #0984e3)",
                                "color": "white",
                                "border-radius": "8px 8px 0 0",
                            },
                        ),
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        dcc.Slider(
                                            id="mosaic-opacity-slider",
                                            min=0.1,
                                            max=1.0,
                                            step=0.1,
                                            value=0.7,
                                            marks={
                                                0.1: {
                                                    "label": "10%",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                0.5: {
                                                    "label": "50%",
                                                    "style": {
                                                        "color": "#0984e3",
                                                        "font-weight": "bold",
                                                        "fontSize": "13px",
                                                    },
                                                },
                                                1.0: {
                                                    "label": "100%",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                            },
                                            tooltip={
                                                "placement": "bottom",
                                                "always_visible": False,
                                                "style": {"fontSize": "12px"},
                                            },
                                            disabled=False,
                                            className="custom-slider",
                                        )
                                    ],
                                    style={
                                        "padding": "5px 10px",
                                        "margin": "0",
                                        "minHeight": "50px",
                                    },
                                )
                            ],
                            className="p-2",
                        ),
                    ],
                    className="mb-1 border-0 shadow-sm",
                    style={"border-radius": "12px"},
                ),
                # Provider and source selection
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-database me-2"),
                                        html.H6("Mosaic Source", className="mb-0"),
                                    ],
                                    className="d-flex align-items-center",
                                )
                            ],
                            className="border-0",
                            style={
                                "background": "linear-gradient(45deg, #55efc4, #00b894)",
                                "color": "#1f2937",
                                "border-radius": "8px 8px 0 0",
                            },
                        ),
                        dbc.CardBody(
                            [
                                html.Small("Provider", className="text-muted d-block mb-1"),
                                dcc.Dropdown(
                                    id="mosaic-provider-selector",
                                    options=[
                                        {"label": "Local MER FITS", "value": "local_fits"},
                                        {"label": "ESA Sky (Public HiPS)", "value": "esa_sky"},
                                    ],
                                    value="esa_sky",
                                    clearable=False,
                                    className="mb-2",
                                ),
                                html.Small("Source", className="text-muted d-block mb-1"),
                                dcc.Dropdown(
                                    id="mosaic-source-selector",
                                    options=[
                                        {"label": "DpdMerBksMosaic", "value": "local_mer"},
                                        {"label": "ESA DSS2 Color", "value": "CDS/P/DSS2/color"},
                                    ],
                                    value="CDS/P/DSS2/color",
                                    clearable=False,
                                ),
                                html.Small(
                                    id="mosaic-source-attribution",
                                    children="Attribution: ESA DSS2 Color",
                                    className="text-muted d-block mt-2",
                                ),
                                html.Div(
                                    [
                                        html.Small(
                                            "Image Format",
                                            className="text-muted d-block mb-1 mt-2",
                                        ),
                                        dcc.Dropdown(
                                            id="mosaic-esa-format-selector",
                                            options=[
                                                {
                                                    "label": "FITS (32-bit, high quality)",
                                                    "value": "fits",
                                                },
                                                {
                                                    "label": "JPEG (8-bit, faster)",
                                                    "value": "jpg",
                                                },
                                            ],
                                            value="jpg",
                                            clearable=False,
                                        ),
                                    ],
                                    id="mosaic-esa-format-container",
                                    style={"display": "block"},
                                ),
                            ],
                            className="p-3",
                        ),
                    ],
                    className="mb-2 border-0 shadow-sm",
                    style={"border-radius": "12px"},
                ),
                # Load mosaic button
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                dbc.Button(
                                    [
                                        html.I(className="fas fa-download me-2"),
                                        "🖼️ Load Mosaic in Zoom",
                                    ],
                                    id="mosaic-render-button",
                                    color="info",
                                    size="sm",
                                    className="w-100 mb-2 shadow-sm btn-enhanced",
                                    n_clicks=0,
                                    disabled=True,
                                    style={"border-radius": "8px", "font-weight": "600"},
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-image me-1"),
                                        "Load mosaic images for visible MER tiles",
                                    ],
                                    className="text-muted d-block text-left mb-2",
                                ),
                                # Mosaic visibility and delete controls
                                html.Div(
                                    [
                                        dbc.Button(
                                            [html.I(className="fas fa-eye me-1"), "Hide Mosaic"],
                                            id="mosaic-toggle-visibility-button",
                                            color="secondary",
                                            size="sm",
                                            outline=True,
                                            className="me-1",
                                            n_clicks=0,
                                            disabled=True,
                                            style={"border-radius": "6px", "font-size": "0.85rem"},
                                        ),
                                        dbc.Button(
                                            [html.I(className="fas fa-trash me-1"), "Delete"],
                                            id="mosaic-delete-button",
                                            color="danger",
                                            size="sm",
                                            outline=True,
                                            n_clicks=0,
                                            disabled=True,
                                            style={"border-radius": "6px", "font-size": "0.85rem"},
                                        ),
                                    ],
                                    className="d-flex justify-content-between",
                                ),
                            ],
                            className="p-3",
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #e8f4f8, #ffffff)",
                        "border-radius": "12px",
                    },
                ),
            ]
        )

    @staticmethod
    def create_healpix_mask_section():
        """Create Healpix mask controls section with opacity slider and load/hide/delete."""
        return html.Div(
            [
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-adjust me-2"),
                                        html.H6("Mask Opacity", className="mb-0"),
                                    ],
                                    className="d-flex align-items-center",
                                )
                            ],
                            className="border-0",
                            style={
                                "background": "linear-gradient(45deg, #74b9ff, #0984e3)",
                                "color": "white",
                                "border-radius": "8px 8px 0 0",
                            },
                        ),
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        dcc.Slider(
                                            id="mask-opacity-slider",
                                            min=0.1,
                                            max=1.0,
                                            step=0.1,
                                            value=0.4,
                                            marks={
                                                0.1: {
                                                    "label": "10%",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                                0.5: {
                                                    "label": "50%",
                                                    "style": {
                                                        "color": "#0984e3",
                                                        "font-weight": "bold",
                                                        "fontSize": "13px",
                                                    },
                                                },
                                                1.0: {
                                                    "label": "100%",
                                                    "style": {"color": "#666", "fontSize": "12px"},
                                                },
                                            },
                                            tooltip={
                                                "placement": "bottom",
                                                "always_visible": False,
                                                "style": {"fontSize": "12px"},
                                            },
                                            disabled=False,
                                            className="custom-slider",
                                        )
                                    ],
                                    style={
                                        "padding": "5px 10px",
                                        "margin": "0",
                                        "minHeight": "50px",
                                    },
                                )
                            ],
                            className="p-2",
                        ),
                    ],
                    className="mb-1 border-0 shadow-sm",
                    style={"border-radius": "12px"},
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                dbc.Button(
                                    [
                                        html.I(className="fas fa-download me-2"),
                                        "🖼️ Healpix Mask in Zoom",
                                    ],
                                    id="healpix-mask-button",
                                    color="info",
                                    size="sm",
                                    className="w-100 mb-2 shadow-sm btn-enhanced",
                                    n_clicks=0,
                                    disabled=True,
                                    style={"border-radius": "8px", "font-weight": "600"},
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-image me-1"),
                                        "Load healpix mask overlay for visible MER tiles",
                                    ],
                                    className="text-muted d-block text-left mb-2",
                                ),
                                # Mask type selector
                                html.Div(
                                    [
                                        html.Label(
                                            "Mask type:",
                                            className="form-label small text-muted mb-1",
                                        ),
                                        dbc.RadioItems(
                                            id="mask-type-selector",
                                            options=[
                                                {
                                                    "label": "Corrected Mask",
                                                    "value": "corrected",
                                                },
                                                {
                                                    "label": "Eff. Coverage Mask",
                                                    "value": "effcov",
                                                },
                                            ],
                                            value="corrected",
                                            inline=True,
                                            className="mb-2",
                                            inputClassName="me-1",
                                            labelClassName="me-3 small",
                                        ),
                                    ],
                                    className="mb-2",
                                ),
                                # Healpix mask visibility and delete controls
                                html.Div(
                                    [
                                        dbc.Button(
                                            [html.I(className="fas fa-eye me-1"), "Hide Mask"],
                                            id="mask-toggle-visibility-button",
                                            color="secondary",
                                            size="sm",
                                            outline=True,
                                            className="me-1",
                                            n_clicks=0,
                                            disabled=True,
                                            style={"border-radius": "6px", "font-size": "0.85rem"},
                                        ),
                                        dbc.Button(
                                            [html.I(className="fas fa-trash me-1"), "Delete"],
                                            id="mask-delete-button",
                                            color="danger",
                                            size="sm",
                                            outline=True,
                                            n_clicks=0,
                                            disabled=True,
                                            style={"border-radius": "6px", "font-size": "0.85rem"},
                                        ),
                                    ],
                                    className="d-flex justify-content-between",
                                ),
                            ],
                            className="p-3",
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #e8f4f8, #ffffff)",
                        "border-radius": "12px",
                    },
                ),
            ],
            className="mt-3",
        )
