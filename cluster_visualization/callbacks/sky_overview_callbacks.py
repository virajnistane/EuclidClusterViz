"""Globe overview callbacks: build the globe figure on the server and ask for new
cells when a zoom or rotation needs another resolution or area.

The globe is drawn only while the Globe view is shown (view-mode-store == "globe").
It is rebuilt when that view is entered, after each Render / Apply filters (both
update rendered-meta-store) and when the browser's tracker bumps globe-request.
"""

import time
import traceback

from dash import Input, Output, State, no_update

# Relative: the app imports this package as `callbacks`, tests as `cluster_visualization.callbacks`
from .main_plot import MainPlotCallbacks
from cluster_visualization.src.visualization.sky_overview import build_sky_overview

# Mirrors sky_overview.view_radius_deg / choose_nside. The figure's layout.meta holds
# the view and nside its cells were computed for; a new request goes out when the
# resolution would change or the centre moves by half the visible radius.
GLOBE_TRACKER_JS = """
function(relayoutData) {
    var dc = window.dash_clientside;
    if (!relayoutData) return dc.no_update;
    var touchesGeo = Object.keys(relayoutData).some(function(k) { return k.indexOf('geo') === 0; });
    if (!touchesGeo) return dc.no_update;

    clearTimeout(window._globeTimer);
    window._globeTimer = setTimeout(function() {
        var host = document.getElementById('sky-overview');
        var gd = host && (host.classList.contains('js-plotly-plot') ? host : host.querySelector('.js-plotly-plot'));
        if (!gd || !gd._fullLayout || !gd._fullLayout.geo || !gd.layout || !gd.layout.meta) return;
        var meta = gd.layout.meta;
        var proj = gd._fullLayout.geo.projection;
        var view = {lon: proj.rotation.lon, lat: proj.rotation.lat, scale: proj.scale || 1};

        var rad = Math.PI / 180;
        var s = Math.max(view.scale, 1);
        var r = Math.min(90, Math.asin(1 / s) / rad * 1.2);
        var frac = 1 - Math.cos(r * rad);
        var limit = Math.sqrt((meta.max_cells || 3000) / (6 * frac));
        var nside = Math.pow(2, Math.floor(Math.log2(Math.max(limit, 1))));
        nside = Math.min(Math.max(nside, 8), meta.nside_max || 1024);

        var last = meta.view || view;
        var cosd = Math.sin(view.lat * rad) * Math.sin(last.lat * rad)
                 + Math.cos(view.lat * rad) * Math.cos(last.lat * rad) * Math.cos((view.lon - last.lon) * rad);
        var moved = Math.acos(Math.max(-1, Math.min(1, cosd))) / rad;

        if (nside === meta.nside && moved <= 0.5 * r) return;
        try {
            fetch('/log', {method: 'POST', body: '[globe] request nside ' + meta.nside + ' -> ' + nside
                + ' moved=' + moved.toFixed(1) + 'deg scale=' + view.scale.toFixed(2)});
        } catch (e) {}
        dc.set_props('globe-request', {data: {
            lon: view.lon, lat: view.lat, scale: view.scale,
            nside: nside, uirevision: meta.uirevision, t: Date.now()
        }});
    }, 300);
    return dc.no_update;
}
"""


class SkyOverviewCallbacks:
    """Globe overview: the 2-D map's density and CL-tile CORE outlines on the sky sphere."""

    def __init__(self, app, data_loader, trace_creator):
        self.app = app
        self.data_loader = data_loader
        self.trace_creator = trace_creator
        self._setup_tracker_callback()
        self._setup_globe_callback()

    def _setup_tracker_callback(self):
        # Returns no_update; the debounced timer sets globe-request via set_props
        self.app.clientside_callback(
            GLOBE_TRACKER_JS,
            Output("globe-request", "data"),
            Input("sky-overview", "relayoutData"),
            prevent_initial_call=True,
        )

    def _setup_globe_callback(self):
        @self.app.callback(
            [
                Output("sky-overview", "figure"),
                Output("sky-overview-empty", "style"),
            ],
            [
                Input("view-mode-store", "data"),
                # Changes after every Render and Apply filters
                Input("rendered-meta-store", "data"),
                Input("globe-request", "data"),
            ],
            [
                State("matching-clusters-switch", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("snr-include-missing-pzwav", "value"),
                State("snr-include-missing-amico", "value"),
                State("redshift-range-slider", "value"),
                State("redshift-include-missing", "value"),
                State("richness-range-slider-zp", "value"),
                State("richness-range-slider-rs", "value"),
                State("richness-include-missing-zp", "value"),
                State("richness-include-missing-rs", "value"),
                State("richness-mode-radio", "value"),
                State("flag-quality-zp-checklist", "value"),
                State("flag-quality-rs-checklist", "value"),
                State("idcluster-upload", "contents"),
                State("idcluster-upload", "filename"),
            ],
            prevent_initial_call=True,
        )
        def update_globe(
            view_mode,
            rendered_meta,
            globe_request,
            matching_clusters,
            snr_range_pzwav,
            snr_range_amico,
            snr_include_missing_pzwav,
            snr_include_missing_amico,
            redshift_range,
            redshift_include_missing,
            richness_range_zp,
            richness_range_rs,
            richness_include_missing_zp,
            richness_include_missing_rs,
            richness_mode,
            flag_quality_zp,
            flag_quality_rs,
            idcluster_upload_contents,
            idcluster_upload_filename,
        ):
            if view_mode != "globe":
                return no_update, no_update
            algorithm = (rendered_meta or {}).get("algorithm")
            if not algorithm or self.trace_creator is None:
                return no_update, {"display": "flex"}

            try:
                kw = MainPlotCallbacks._resolve_filter_kwargs(
                    snr_range_pzwav, snr_range_amico,
                    snr_include_missing_pzwav, snr_include_missing_amico,
                    redshift_range, redshift_include_missing,
                    richness_range_zp, richness_range_rs,
                    richness_include_missing_zp, richness_include_missing_rs,
                    richness_mode, flag_quality_zp, flag_quality_rs,
                    idcluster_upload_contents, idcluster_upload_filename,
                )
                _t = time.perf_counter()
                data = self.data_loader.load_data(algorithm)
                uirevision = f"globe-{algorithm}"
                # A request made on another catalog's globe would centre on the wrong area
                view = (
                    globe_request
                    if globe_request and globe_request.get("uirevision") == uirevision
                    else None
                )
                fig, summary = build_sky_overview(
                    data,
                    self.trace_creator,
                    kw,
                    view=view,
                    matching_clusters=bool(matching_clusters),
                    uirevision=uirevision,
                )
                print(
                    f"Globe [nside={summary['nside']}, cells={summary['cells']}, "
                    f"clusters={summary['clusters']}] in {time.perf_counter() - _t:.2f}s"
                )
                return fig, {"display": "none"}
            except Exception as e:
                print(f"Error: globe overview failed: {e}")
                traceback.print_exc()
                return no_update, no_update
