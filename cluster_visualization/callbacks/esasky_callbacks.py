"""
ESASky API integration callbacks for sky viewer functionality.

This module provides clientside callbacks to integrate the ESASky JavaScript
API into the Dash application, enabling interactive sky visualization with
synchronization to cluster plot interactions.

ESASky API Documentation: https://www.cosmos.esa.int/web/esdc/esasky-javascript-api
API Events: goToRaDec, setFov, getFov, getCenter, setHiPS, etc.
"""
from dash import Input, Output, State, clientside_callback, html
import dash_bootstrap_components as dbc


class ESASkyCallbacks:
    """Handles ESASky viewer callbacks using postMessage API"""

    def __init__(self, app):
        """
        Initialize ESASky callbacks.

        Args:
            app: Dash application instance
        """
        self.app = app
        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all ESASky-related callbacks"""
        self._setup_esasky_initialization()
        self._setup_esasky_main_initialization()
        self._setup_esasky_update_from_click()
        self._setup_main_view_toggle()
        self._setup_esasky_sync_with_plot()
        self._setup_esasky_controls()
        self._setup_esasky_main_controls()

    def _setup_esasky_initialization(self):
        """Initialize ESASky iframe when tab is first opened"""
        clientside_callback(
            """
            function(activeTab) {
                if (activeTab === 'esasky-tab' && !window.esaskyInstance) {
                    // Initialize ESASky instance
                    const iframe = document.getElementById('esasky-iframe');
                    if (iframe) {
                        window.esaskyInstance = iframe.contentWindow;
                        console.log('ESASky iframe initialized');
                    }
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("esasky-iframe", "data-initialized"),
            Input("analysis-tabs", "active_tab"),
        )

    def _setup_esasky_main_initialization(self):
        """Initialize ESASky viewer as overlay"""
        clientside_callback(
            """
            function(toggleClicks) {
                if (toggleClicks && !window.esaskyMainInstance) {
                    const iframe = document.getElementById('esasky-main-iframe');
                    if (iframe) {
                        window.esaskyMainInstance = iframe.contentWindow;
                        console.log('ESASky overlay iframe initialized');
                    }
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("esasky-main-iframe", "data-initialized"),
            Input("toggle-esasky-overlay-btn", "n_clicks"),
        )

    def _setup_esasky_update_from_click(self):
        """Update ESASky tab view when cluster is clicked"""
        clientside_callback(
            """
            function(clickData, activeTab) {
                if (!clickData || !clickData.points || activeTab !== 'esasky-tab') {
                    return window.dash_clientside.no_update;
                }
                
                if (!window.esaskyInstance) {
                    const iframe = document.getElementById('esasky-iframe');
                    if (iframe) {
                        window.esaskyInstance = iframe.contentWindow;
                    }
                }
                
                if (window.esaskyInstance) {
                    const ra = clickData.points[0].x;
                    const dec = clickData.points[0].y;
                    
                    // Send goToRaDec command via postMessage
                    window.esaskyInstance.postMessage({
                        event: 'goToRaDec',
                        content: {
                            ra: ra.toString(),
                            dec: dec.toString()
                        }
                    }, '*');
                    
                    console.log(`ESASky centered on RA: ${ra.toFixed(4)}, Dec: ${dec.toFixed(4)}`);
                }
                
                return window.dash_clientside.no_update;
            }
            """,
            Output("esasky-iframe", "data-updated"),
            [Input("cluster-plot", "clickData")],
            [State("analysis-tabs", "active_tab")],
        )

    def _setup_main_view_toggle(self):
        """Toggle ESASky overlay visibility and sync with cluster plot zoom"""
        clientside_callback(
            """
            function(toggleClicks, relayoutData) {
                if (window.esaskyOverlayVisible === undefined) {
                    window.esaskyOverlayVisible = false;
                }
                
                const ctx = window.dash_clientside.callback_context;
                if (!ctx.triggered.length) {
                    return [
                        {
                            'position': 'absolute',
                            'top': '0',
                            'left': '0',
                            'width': '100%',
                            'height': '100%',
                            'opacity': '0',
                            'pointer-events': 'none',
                            'transition': 'opacity 0.3s ease-in-out',
                            'z-index': '10'
                        },
                        'info',
                        true
                    ];
                }
                
                window.esaskyOverlayVisible = !window.esaskyOverlayVisible;
                
                if (window.esaskyOverlayVisible) {
                    // Initialize iframe if needed
                    if (!window.esaskyMainInstance) {
                        const iframe = document.getElementById('esasky-main-iframe');
                        if (iframe) {
                            window.esaskyMainInstance = iframe.contentWindow;
                        }
                    }
                    
                    // Show overlay and sync with plot
                    setTimeout(() => {
                        if (window.esaskyMainInstance) {
                            if (relayoutData && relayoutData['xaxis.range[0]'] !== undefined) {
                                const raMin = relayoutData['xaxis.range[0]'];
                                const raMax = relayoutData['xaxis.range[1]'];
                                const decMin = relayoutData['yaxis.range[0]'];
                                const decMax = relayoutData['yaxis.range[1]'];
                                
                                const raCen = (raMin + raMax) / 2;
                                const decCen = (decMin + decMax) / 2;
                                const raSpan = Math.abs(raMax - raMin);
                                const decSpan = Math.abs(decMax - decMin);
                                const fov = Math.max(raSpan, decSpan);
                                
                                console.log(`ESASky overlay: RA ${raCen.toFixed(4)}, Dec ${decCen.toFixed(4)}, FOV ${fov.toFixed(4)}°`);
                                
                                // Send commands to ESASky
                                window.esaskyMainInstance.postMessage({
                                    event: 'goToRaDec',
                                    content: {
                                        ra: raCen.toString(),
                                        dec: decCen.toString()
                                    }
                                }, '*');
                                
                                window.esaskyMainInstance.postMessage({
                                    event: 'setFov',
                                    content: {
                                        fov: fov.toString()
                                    }
                                }, '*');
                            }
                        }
                    }, 100);
                    
                    return [
                        {
                            'position': 'absolute',
                            'top': '0',
                            'left': '0',
                            'width': '100%',
                            'height': '100%',
                            'opacity': '0.95',
                            'pointer-events': 'auto',
                            'transition': 'opacity 0.3s ease-in-out',
                            'z-index': '10'
                        },
                        'info',
                        false
                    ];
                } else {
                    return [
                        {
                            'position': 'absolute',
                            'top': '0',
                            'left': '0',
                            'width': '100%',
                            'height': '100%',
                            'opacity': '0',
                            'pointer-events': 'none',
                            'transition': 'opacity 0.3s ease-in-out',
                            'z-index': '10'
                        },
                        'info',
                        true
                    ];
                }
            }
            """,
            [
                Output("esasky-main-container", "style"),
                Output("toggle-esasky-overlay-btn", "color"),
                Output("toggle-esasky-overlay-btn", "outline"),
            ],
            [
                Input("toggle-esasky-overlay-btn", "n_clicks"),
            ],
            [State("cluster-plot", "relayoutData")],
        )

    def _setup_esasky_sync_with_plot(self):
        """Sync ESASky overlay with cluster plot zoom/pan changes in real-time"""
        clientside_callback(
            """
            function(relayoutData) {
                if (!window.esaskyOverlayVisible || !window.esaskyMainInstance) {
                    return window.dash_clientside.no_update;
                }
                
                if (relayoutData && relayoutData['xaxis.range[0]'] !== undefined) {
                    const raMin = relayoutData['xaxis.range[0]'];
                    const raMax = relayoutData['xaxis.range[1]'];
                    const decMin = relayoutData['yaxis.range[0]'];
                    const decMax = relayoutData['yaxis.range[1]'];
                    
                    const raCen = (raMin + raMax) / 2;
                    const decCen = (decMin + decMax) / 2;
                    const raSpan = Math.abs(raMax - raMin);
                    const decSpan = Math.abs(decMax - decMin);
                    const fov = Math.max(raSpan, decSpan);
                    
                    // Update ESASky to match new view
                    window.esaskyMainInstance.postMessage({
                        event: 'goToRaDec',
                        content: {
                            ra: raCen.toString(),
                            dec: decCen.toString()
                        }
                    }, '*');
                    
                    window.esaskyMainInstance.postMessage({
                        event: 'setFov',
                        content: {
                            fov: fov.toString()
                        }
                    }, '*');
                    
                    console.log(`ESASky synced: RA ${raCen.toFixed(4)}, Dec ${decCen.toFixed(4)}, FOV ${fov.toFixed(4)}°`);
                }
                
                return window.dash_clientside.no_update;
            }
            """,
            Output("esasky-main-iframe", "data-synced"),
            Input("cluster-plot", "relayoutData"),
        )

    def _setup_esasky_controls(self):
        """Update ESASky tab view from controls"""
        clientside_callback(
            """
            function(survey, fov, clickData) {
                if (!window.esaskyInstance) {
                    const iframe = document.getElementById('esasky-iframe');
                    if (iframe) {
                        window.esaskyInstance = iframe.contentWindow;
                    }
                }
                
                if (!window.esaskyInstance) {
                    return window.dash_clientside.no_update;
                }
                
                const ctx = window.dash_clientside.callback_context;
                if (!ctx.triggered.length) {
                    return window.dash_clientside.no_update;
                }
                
                const triggeredId = ctx.triggered[0].prop_id.split('.')[0];
                
                if (triggeredId === 'esasky-survey' && survey) {
                    window.esaskyInstance.postMessage({
                        event: 'setHiPS',
                        content: {
                            hipsName: survey
                        }
                    }, '*');
                    console.log(`ESASky survey changed to: ${survey}`);
                }
                
                if (triggeredId === 'esasky-fov' && fov && fov > 0) {
                    window.esaskyInstance.postMessage({
                        event: 'setFov',
                        content: {
                            fov: fov.toString()
                        }
                    }, '*');
                    console.log(`ESASky FOV changed to: ${fov}°`);
                }
                
                if (triggeredId === 'cluster-plot' && clickData && clickData.points) {
                    const ra = clickData.points[0].x;
                    const dec = clickData.points[0].y;
                    
                    window.esaskyInstance.postMessage({
                        event: 'goToRaDec',
                        content: {
                            ra: ra.toString(),
                            dec: dec.toString()
                        }
                    }, '*');
                    
                    console.log(`ESASky navigated to: RA ${ra.toFixed(4)}, Dec ${dec.toFixed(4)}`);
                }
                
                return window.dash_clientside.no_update;
            }
            """,
            Output("esasky-iframe", "data-control-updated"),
            [
                Input("esasky-survey", "value"),
                Input("esasky-fov", "value"),
                Input("cluster-plot", "clickData"),
            ],
            [State("analysis-tabs", "active_tab")],
        )

    def _setup_esasky_main_controls(self):
        """Update ESASky main view from controls"""
        clientside_callback(
            """
            function(survey, fov, clickData) {
                if (!window.esaskyMainInstance) {
                    return window.dash_clientside.no_update;
                }
                
                const ctx = window.dash_clientside.callback_context;
                if (!ctx.triggered.length) {
                    return window.dash_clientside.no_update;
                }
                
                const triggeredId = ctx.triggered[0].prop_id.split('.')[0];
                
                if (triggeredId === 'esasky-main-survey' && survey) {
                    window.esaskyMainInstance.postMessage({
                        event: 'setHiPS',
                        content: {
                            hipsName: survey
                        }
                    }, '*');
                    console.log(`ESASky (main) survey changed to: ${survey}`);
                }
                
                if (triggeredId === 'esasky-main-fov' && fov && fov > 0) {
                    window.esaskyMainInstance.postMessage({
                        event: 'setFov',
                        content: {
                            fov: fov.toString()
                        }
                    }, '*');
                    console.log(`ESASky (main) FOV changed to: ${fov}°`);
                }
                
                if (triggeredId === 'cluster-plot' && clickData && clickData.points) {
                    const ra = clickData.points[0].x;
                    const dec = clickData.points[0].y;
                    
                    window.esaskyMainInstance.postMessage({
                        event: 'goToRaDec',
                        content: {
                            ra: ra.toString(),
                            dec: dec.toString()
                        }
                    }, '*');
                }
                
                return window.dash_clientside.no_update;
            }
            """,
            Output("esasky-main-iframe", "data-control-updated"),
            [
                Input("esasky-main-survey", "value"),
                Input("esasky-main-fov", "value"),
                Input("cluster-plot", "clickData"),
            ],
        )
