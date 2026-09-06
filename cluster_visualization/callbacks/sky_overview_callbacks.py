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


# Globe <-> map handoff: one zoomable sky. Zooming the globe in below map_enter_fov shows
# the 2-D map at the same place; zooming the map out past globe_enter_fov (or the Globe
# button) shows the globe centred where the map was; a Render starts wide catalogs on
# the globe. Programmatic view changes go through the Dash figure props (set_props), as
# a bare Plotly.relayout is undone by the next server update (uirevision keeps only
# user edits).
HANDOFF_JS = r"""
function(globeRelayout, mapRelayout, renderedMeta, globeClicks, mode, settings, mapFig, globeFig) {
    var dc = window.dash_clientside;
    var NU = dc.no_update;
    var RAD = Math.PI / 180;
    var S = window.cvSky = window.cvSky || {
        fovForScale: function(scale) {
            scale = scale || 1;
            return scale <= 1 ? 180 : 2 * Math.asin(1 / scale) / RAD;
        },
        scaleForFov: function(fov) {
            return fov >= 180 ? 1 : 1 / Math.sin(Math.max(fov, 1e-3) / 2 * RAD);
        },
        wrap180: function(x) { return ((x + 180) % 360 + 360) % 360 - 180; },
        wrap360: function(x) { return (x % 360 + 360) % 360; },
        // Map axis ranges (RA axis reversed) showing `fov` degrees around (ra, dec)
        mapRanges: function(ra, dec, fov) {
            var half = fov / 2;
            var halfRa = half / Math.max(Math.cos(dec * RAD), 0.05);
            return {x: [ra + halfRa, ra - halfRa],
                    y: [Math.max(dec - half, -90), Math.min(dec + half, 90)]};
        },
        // Centre and angular span (deg) of map axis ranges
        mapView: function(xr, yr) {
            var ra0 = Math.min(xr[0], xr[1]), ra1 = Math.max(xr[0], xr[1]);
            var d0 = Math.min(yr[0], yr[1]), d1 = Math.max(yr[0], yr[1]);
            var dec = (d0 + d1) / 2;
            return {ra: S.wrap360((ra0 + ra1) / 2), dec: dec,
                    span: Math.max((ra1 - ra0) * Math.cos(dec * RAD), d1 - d0)};
        }
    };
    if (mode !== 'plotly' && mode !== 'globe') return NU;  // Aladin / ESA Sky: not ours

    var ctx = dc.callback_context || {};
    var trig = (ctx.triggered || []).map(function(t) { return t.prop_id || ''; }).join(' ');
    settings = settings || {};
    var mapEnter = settings.map_enter_fov || 8;
    var globeEnter = settings.globe_enter_fov || 15;
    var now = Date.now();
    var settling = window._cvHandoffUntil && now < window._cvHandoffUntil;
    var algorithm = renderedMeta && renderedMeta.algorithm;
    var hasMap = !!(mapFig && mapFig.layout && mapFig.data && mapFig.data.length && algorithm);

    function gdOf(id) {
        var host = document.getElementById(id);
        if (!host) return null;
        return (host.classList && host.classList.contains('js-plotly-plot')) ? host
            : (host.querySelector ? host.querySelector('.js-plotly-plot') : null);
    }
    function log(msg) {
        try { fetch('/log', {method: 'POST', body: '[handoff] ' + msg}); } catch (e) {}
    }
    function mapRangesNow() {
        // Ranges on screen (covers autoscale, where relayoutData has none); relayoutData
        // first when it carries both axes
        var r = mapRelayout || {};
        if ('xaxis.range[0]' in r && 'yaxis.range[0]' in r) {
            return [[r['xaxis.range[0]'], r['xaxis.range[1]']], [r['yaxis.range[0]'], r['yaxis.range[1]']]];
        }
        var gd = gdOf('cluster-plot');
        var fl = gd && gd._fullLayout;
        if (fl && fl.xaxis && fl.yaxis && fl.xaxis.range && fl.yaxis.range) {
            return [fl.xaxis.range.slice(), fl.yaxis.range.slice()];
        }
        return null;
    }
    function globeViewNow() {
        var gd = gdOf('sky-overview');
        var p = gd && gd._fullLayout && gd._fullLayout.geo && gd._fullLayout.geo.projection;
        if (!p) {
            var lay = globeFig && globeFig.layout && globeFig.layout.geo;
            p = lay && lay.projection;
        }
        if (!p || !p.rotation) return null;
        return {lon: p.rotation.lon || 0, lat: p.rotation.lat || 0, scale: p.scale || 1};
    }

    function toGlobe(view, why) {
        // view: {lon, lat, scale}, or null to fit the catalog
        window._cvHandoffUntil = Date.now() + 600;
        var uirev = 'globe-' + algorithm;
        if (view && globeFig && globeFig.layout && globeFig.layout.geo) {
            var lay = globeFig.layout;
            var proj = Object.assign({}, lay.geo.projection || {},
                                     {rotation: {lon: view.lon, lat: view.lat}, scale: view.scale});
            dc.set_props('sky-overview', {figure: Object.assign({}, globeFig, {layout: Object.assign({}, lay, {
                geo: Object.assign({}, lay.geo, {projection: proj}),
                uirevision: 'handoff-' + Date.now()   // new value: these projection values win
            })})});
        }
        var req = view ? {lon: view.lon, lat: view.lat, scale: view.scale}
                       : {fit: true};
        req.uirevision = uirev;
        req.t = Date.now();
        dc.set_props('globe-request', {data: req});
        log('-> globe (' + why + ')' + (view ? ' scale=' + view.scale.toFixed(2) : ' fit'));
        return 'globe';
    }

    function toMap(ra, dec, fov, why) {
        window._cvHandoffUntil = Date.now() + 600;
        var rg = S.mapRanges(ra, dec, fov);
        var lay = mapFig.layout;
        var fig = Object.assign({}, mapFig, {layout: Object.assign({}, lay, {
            xaxis: Object.assign({}, lay.xaxis || {}, {range: rg.x, autorange: false}),
            yaxis: Object.assign({}, lay.yaxis || {}, {range: rg.y, autorange: false}),
            uirevision: 'handoff-' + Date.now()       // new value: these ranges win
        })});
        dc.set_props('cluster-plot', {figure: fig});
        // Once the map has redrawn with the new ranges, replay them as a relayout so the
        // viewport tracker (and Aladin / mosaic gates) see the new area
        var tries = 0;
        (function replay() {
            var gd = gdOf('cluster-plot');
            var fl = gd && gd._fullLayout;
            var ok = fl && fl.xaxis && fl.xaxis.range &&
                     Math.abs(fl.xaxis.range[0] - rg.x[0]) + Math.abs(fl.xaxis.range[1] - rg.x[1]) < 1e-6;
            if (ok && window.Plotly && window.Plotly.Plots) {
                window.Plotly.Plots.resize(gd);
                window.Plotly.relayout(gd, {'xaxis.range[0]': rg.x[0], 'xaxis.range[1]': rg.x[1],
                                            'yaxis.range[0]': rg.y[0], 'yaxis.range[1]': rg.y[1]});
            } else if (tries++ < 40) {
                setTimeout(replay, 50);
            }
        })();
        log('-> map (' + why + ') ra=' + ra.toFixed(2) + ' dec=' + dec.toFixed(2) + ' fov=' + fov.toFixed(2));
        return 'plotly';
    }

    // A new Render: wide catalogs start on the globe, others on the map
    if (trig.indexOf('rendered-meta-store') >= 0) {
        if (!renderedMeta || !renderedMeta.rendered_at || renderedMeta.rendered_at === window._cvLastRender) return NU;
        window._cvLastRender = renderedMeta.rendered_at;
        var span = renderedMeta.span || 0;
        var xr = mapFig && mapFig.layout && mapFig.layout.xaxis && mapFig.layout.xaxis.range;
        var yr = mapFig && mapFig.layout && mapFig.layout.yaxis && mapFig.layout.yaxis.range;
        if (xr && yr && xr.length === 2 && yr.length === 2) span = S.mapView(xr, yr).span;  // kept zoom
        if (span > globeEnter) return mode === 'globe' ? (toGlobe(null, 'render'), NU) : toGlobe(null, 'render');
        return mode === 'plotly' ? NU : 'plotly';
    }

    // Globe button: the globe at the map's current view
    if (trig.indexOf('view-mode-globe-btn') >= 0) {
        var rgB = hasMap && mapRangesNow();
        if (!rgB) return NU;  // the button's own callback switches the mode
        var vB = S.mapView(rgB[0], rgB[1]);
        return toGlobe({lon: S.wrap180(-vB.ra), lat: vB.dec,
                        scale: S.scaleForFov(Math.max(vB.span, globeEnter))}, 'button');
    }

    if (settling) return NU;  // relayouts caused by the handoff itself

    // Globe zoomed in: hand over to the map
    if (mode === 'globe' && trig.indexOf('sky-overview.relayoutData') >= 0 && hasMap) {
        var g = globeViewNow();
        if (!g) return NU;
        var fov = S.fovForScale(g.scale);
        if (fov >= mapEnter) return NU;
        return toMap(S.wrap360(-g.lon), g.lat, fov, 'zoom in, fov ' + fov.toFixed(1));
    }

    // Map zoomed out: hand back to the globe
    if (mode === 'plotly' && trig.indexOf('cluster-plot.relayoutData') >= 0 && hasMap) {
        var rg = mapRangesNow();
        if (!rg) return NU;
        var v = S.mapView(rg[0], rg[1]);
        if (!(v.span > globeEnter)) return NU;
        return toGlobe({lon: S.wrap180(-v.ra), lat: v.dec, scale: S.scaleForFov(v.span)},
                       'zoom out, span ' + v.span.toFixed(1));
    }
    return NU;
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
        self._setup_handoff_callback()

    def _setup_tracker_callback(self):
        # Returns no_update; the debounced timer sets globe-request via set_props
        self.app.clientside_callback(
            GLOBE_TRACKER_JS,
            Output("globe-request", "data"),
            Input("sky-overview", "relayoutData"),
            prevent_initial_call=True,
        )

    def _setup_handoff_callback(self):
        self.app.clientside_callback(
            HANDOFF_JS,
            Output("view-mode-store", "data", allow_duplicate=True),
            [
                Input("sky-overview", "relayoutData"),
                Input("cluster-plot", "relayoutData"),
                Input("rendered-meta-store", "data"),
                Input("view-mode-globe-btn", "n_clicks"),
            ],
            [
                State("view-mode-store", "data"),
                State("sky-view-settings", "data"),
                State("cluster-plot", "figure"),
                State("sky-overview", "figure"),
            ],
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
                State("ned-specz-filter-switch", "value"),
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
            ned_specz_filter,
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
                    ned_specz_filter=ned_specz_filter,
                )
                _t = time.perf_counter()
                data = self.data_loader.load_data(algorithm)
                uirevision = f"globe-{algorithm}"
                # A request made on another catalog's globe would centre on the wrong area;
                # {"fit": true} (a new Render) asks for the catalog-fitting view
                view = (
                    globe_request
                    if globe_request
                    and globe_request.get("uirevision") == uirevision
                    and not globe_request.get("fit")
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
