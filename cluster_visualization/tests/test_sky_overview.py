"""Globe overview: HEALPix aggregation, resolution choice, geometry and figure."""

import json
import math
import os
import tempfile
import unittest

import numpy as np
import plotly.utils

from cluster_visualization.src.visualization import sky_overview as so
from cluster_visualization.src.visualization.traces import TraceCreator
from cluster_visualization.tests.test_incremental_render import FILTERS, make_data

try:
    import healpy  # noqa: F401

    HAVE_HEALPY = True
except ImportError:  # pragma: no cover
    HAVE_HEALPY = False


def full_sky(n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    ra = rng.uniform(0, 360, n)
    dec = np.degrees(np.arcsin(rng.uniform(-1, 1, n)))
    return ra, dec


def ring_area(ring):
    """Signed area (sr, small-cell approximation) of a closed (lon, lat) ring;
    negative = clockwise."""
    pts = np.asarray(ring[:-1], dtype=float)
    lon, lat = pts[:, 0], pts[:, 1]
    x = np.radians(lon) * np.cos(np.radians(lat.mean()))
    y = np.radians(lat)
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


@unittest.skipUnless(HAVE_HEALPY, "healpy not installed")
class TestHealpixAggregation(unittest.TestCase):
    def test_counts_sum_to_n_and_coarsening_matches_direct(self):
        ra, dec = full_sky(50_000)
        fine = so.healpix_pixels(ra, dec, 1024)
        for nside in (8, 64, 256):
            pix, counts = so.hpx_counts(fine, 1024, nside)
            self.assertEqual(int(counts.sum()), len(ra))
            direct_pix, direct_counts = np.unique(so.healpix_pixels(ra, dec, nside), return_counts=True)
            np.testing.assert_array_equal(pix, direct_pix)
            np.testing.assert_array_equal(counts, direct_counts)

    def test_non_finite_positions_are_flagged(self):
        pix = so.healpix_pixels(np.array([10.0, np.nan]), np.array([5.0, 3.0]), 64)
        self.assertGreaterEqual(pix[0], 0)
        self.assertEqual(pix[1], -1)

    def test_choose_nside_monotone_and_bounded(self):
        scales = [1, 1.5, 3, 10, 40, 200, 2000]
        nsides = [so.choose_nside(s, 1024, 3000) for s in scales]
        self.assertEqual(nsides, sorted(nsides))
        self.assertTrue(all(so.MIN_NSIDE <= n <= 1024 for n in nsides))
        self.assertTrue(all(n & (n - 1) == 0 for n in nsides))
        self.assertEqual(so.choose_nside(1e6, 256, 3000), 256)

    def test_visible_cells_within_budget(self):
        ra, dec = full_sky(1_000_000)
        fine = so.healpix_pixels(ra, dec, 1024)
        for scale in (1, 2, 5, 20, 80):
            nside = so.choose_nside(scale, 1024, 3000)
            pix, _ = so.hpx_counts(fine, 1024, nside)
            visible = np.isin(pix, so.visible_pixels(nside, -50.0, -30.0, scale))
            # query_disc(inclusive) adds a ring of edge cells beyond the disc estimate
            self.assertLessEqual(int(visible.sum()), 3000 * 1.5, f"scale {scale}")

    def test_visible_pixels_centre_uses_lon_minus_ra(self):
        import healpy as hp

        nside = 64
        # Globe rotated to lon = -52 (RA 52), lat -28: the cell at RA 52 must be visible
        centre = hp.ang2pix(nside, 52.0, -28.0, nest=True, lonlat=True)
        far = hp.ang2pix(nside, 232.0, 28.0, nest=True, lonlat=True)
        visible = so.visible_pixels(nside, -52.0, -28.0, 20.0)
        self.assertIn(centre, visible)
        self.assertNotIn(far, visible)


@unittest.skipUnless(HAVE_HEALPY, "healpy not installed")
class TestNormalizeView(unittest.TestCase):
    def test_in_range_view_unchanged(self):
        self.assertEqual(so.normalize_view({"lon": -52.0, "lat": -28.0, "scale": 2.0}),
                         {"lon": -52.0, "lat": -28.0, "scale": 2.0})

    def test_past_the_pole_folds_to_the_same_centre(self):
        def centre(view):
            lon, lat = math.radians(view["lon"]), math.radians(view["lat"])
            return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))

        for lon, lat in ((-52.0, -97.5), (10.0, 120.0), (170.0, 95.0), (0.0, 270.0), (-179.0, -181.0)):
            raw = {"lon": lon, "lat": lat, "scale": 1.0}
            fixed = so.normalize_view(raw)
            self.assertTrue(-90.0 <= fixed["lat"] <= 90.0, fixed)
            self.assertTrue(-180.0 <= fixed["lon"] < 180.0, fixed)
            for a, b in zip(centre(raw), centre(fixed)):
                self.assertAlmostEqual(a, b, places=9)


class TestGeometry(unittest.TestCase):
    def test_cells_are_small_clockwise_rings_with_lon_minus_ra(self):
        import healpy as hp

        for nside in (8, 64, 1024):
            pixels = np.array([0, 5, 12 * nside * nside // 2, 12 * nside * nside - 1])
            gj = so.cell_geojson(pixels, nside)
            self.assertEqual(len(gj["features"]), len(pixels))
            cell_area = 4 * math.pi / (12 * nside * nside)
            for feat, pix in zip(gj["features"], pixels):
                ring = feat["geometry"]["coordinates"][0]
                self.assertEqual(ring[0], ring[-1])
                area = ring_area(ring)
                self.assertLess(area, 0, "ring must be clockwise for d3-geo")
                self.assertLess(abs(area), 3 * cell_area)
                # The cell centre (lon = -RA) lies inside the ring's lat range and near its lons
                ra_c, dec_c = hp.pix2ang(nside, int(pix), nest=True, lonlat=True)
                lon = np.array([p[0] for p in ring])
                d_lon = (-ra_c - lon + 180.0) % 360.0 - 180.0
                self.assertLess(np.abs(d_lon).min(), 360.0 / nside + 1.0)
                lats = [p[1] for p in ring]
                self.assertTrue(min(lats) - 1e-6 <= dec_c <= max(lats) + 1e-6)

    def test_ring_crossing_lon_180_is_unwrapped(self):
        ring = so._clockwise_ring(np.array([179.0, -179.0, -179.0, 179.0]), np.array([0.0, 0.0, 1.0, 1.0]))
        lons = [p[0] for p in ring]
        self.assertLess(max(lons) - min(lons), 3.0)
        self.assertLess(ring_area(ring), 0)

    def test_default_view_centres_catalog_across_ra_zero(self):
        ra = np.concatenate([np.linspace(355, 359.9, 50), np.linspace(0, 5, 50)])
        dec = np.full(100, 10.0)
        view = so.default_view(ra, dec)
        self.assertLess(abs(view["lon"]), 1.0)  # centre RA ~0 -> lon ~0
        self.assertAlmostEqual(view["lat"], 10.0, places=3)
        self.assertGreater(view["scale"], 5)


@unittest.skipUnless(HAVE_HEALPY, "healpy not installed")
class TestGlobeFigure(unittest.TestCase):
    def setUp(self):
        self.creator = TraceCreator()
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _with_tile_defs(self, data):
        for key, value in data["data_detcluster_by_cltile"].items():
            ra0 = 50.0 if value["tile_id"] in (1, 3) else 52.0
            poly = [[ra0, -30.0], [ra0 + 2, -30.0], [ra0 + 2, -26.0], [ra0, -26.0]]
            path = os.path.join(self.tmp.name, f"tile_{key}.json")
            with open(path, "w") as f:
                json.dump({"LEV1": {"POLYGON": [poly]}, "CORE": {"POLYGON": [poly]}}, f)
            value["cltiledef_file"] = path
        return data

    def test_selected_clusters_matches_marker_traces(self):
        data = make_data(n=600)
        rows = self.creator.selected_clusters(data, **FILTERS)
        traces = self.creator.create_cluster_traces(data, **FILTERS)
        shown = sum(len(t.x) for t in traces if t.name in ("Merged PZWAV", "Merged AMICO"))
        self.assertEqual(len(rows), shown)

    def test_figure_traces_counts_and_binary(self):
        data = self._with_tile_defs(make_data(n=800))
        fig, summary = so.build_sky_overview(data, self.creator, FILTERS)
        self.assertEqual(fig.data[0].name, so.DENSITY_TRACE)
        self.assertEqual(fig.data[0].type, "choropleth")
        self.assertEqual([list(c) for c in fig.data[0].colorscale],
                         [list(c) for c in TraceCreator.DENSITY_COLORSCALE])
        self.assertEqual(fig.layout.geo.projection.type, "orthographic")

        rows = self.creator.selected_clusters(data, **FILTERS)
        self.assertEqual(summary["clusters"], len(rows))
        self.assertEqual(int(np.sum(fig.data[0].customdata[:, 2])), len(rows))

        # The map's CORE outlines only (per-tile colours), drawn at lon = -RA
        polys = []
        for key, value in data["data_detcluster_by_cltile"].items():
            self.creator._create_cltile_polygons(polys, data, value["tile_id"], value, False, False)
        flat = self.creator._merge_polygon_traces([t for t in polys if "CORE" in t.name])
        geo = fig.data[1:]
        self.assertEqual([t.name for t in geo], [t.name for t in flat])
        for g, m in zip(geo, flat):
            self.assertEqual(g.type, "scattergeo")
            self.assertIn("CORE", g.name)
            self.assertIn(g.fill, (None, "none"))
            self.assertEqual((g.line.color, g.line.dash), (m.line.color, m.line.dash))
            np.testing.assert_allclose(np.asarray(g.lon, float), -np.asarray(m.x, float))
            np.testing.assert_allclose(np.asarray(g.lat, float), np.asarray(m.y, float))

        # CORE hover carries the filtered count of each tile; counts add up
        core_texts = {t for g in geo
                      for t in (g.text if isinstance(g.text, (list, tuple)) else [g.text]) if t}
        tile_total = sum(int(t.split("<br>")[1].split()[0].replace(",", "")) for t in core_texts)
        self.assertEqual(tile_total, len(rows))

        payload = json.dumps(fig.to_plotly_json(), cls=plotly.utils.PlotlyJSONEncoder)
        self.assertIn("bdata", payload)
        self.assertEqual(fig.layout.meta["nside"], summary["nside"])

    def test_view_past_a_pole_does_not_crash(self):
        # Plotly lets the orthographic rotation go past +-90 (globe dragged over a pole);
        # healpy rejected it with "THETA is out of range [0,pi]"
        data = make_data(n=400)
        for lat in (-97.5, 120.0, 270.0):
            fig, summary = so.build_sky_overview(
                data, self.creator, {}, view={"lon": -52, "lat": lat, "scale": 3}
            )
            view = fig.layout.meta["view"]
            self.assertTrue(-90.0 <= view["lat"] <= 90.0, view)
            self.assertTrue(-180.0 <= view["lon"] < 180.0, view)

    def test_view_request_changes_resolution(self):
        data = make_data(n=400)
        coarse, s1 = so.build_sky_overview(data, self.creator, {}, view={"lon": -52, "lat": -28, "scale": 1})
        fine, s2 = so.build_sky_overview(data, self.creator, {}, view={"lon": -52, "lat": -28, "scale": 30})
        self.assertLess(s1["nside"], s2["nside"])
        self.assertEqual(int(np.sum(coarse.data[0].customdata[:, 2])), 400)
        self.assertEqual(fine.layout.meta["view"]["scale"], 30.0)

    def test_row_cache_column_reused(self):
        data = make_data(n=300)
        so.build_sky_overview(data, self.creator, {})
        key = f"hpx{so.GLOBE_SETTINGS['nside_max']}"
        first = data["_render_row_cache"][key]
        self.assertEqual(len(first), 300)
        so.build_sky_overview(data, self.creator, FILTERS)
        self.assertIs(data["_render_row_cache"][key], first)

    def test_globe_settings_from_config(self):
        import configparser

        from cluster_visualization.src.config import Config

        cfg = Config.__new__(Config)
        cfg.config_parser = configparser.ConfigParser()
        cfg.config_parser.read_string("[view]\nnside_max = 512\nglobe_max_cells = x\n")
        got = cfg.get_globe_settings()
        self.assertEqual((got["nside_max"], got["globe_max_cells"]), (512, 3000))

        saved = dict(so.GLOBE_SETTINGS)
        try:
            so.configure_globe(nside_max=1000, globe_max_cells=50)
            self.assertEqual((so.GLOBE_SETTINGS["nside_max"], so.GLOBE_SETTINGS["globe_max_cells"]), (1024, 100))
        finally:
            so.GLOBE_SETTINGS.update(saved)


if __name__ == "__main__":
    unittest.main()


class TestHandoffHelpers(unittest.TestCase):
    def test_fov_scale_round_trip(self):
        for fov in (0.5, 5, 8, 15, 60, 120, 179):
            self.assertAlmostEqual(so.fov_for_scale(so.scale_for_fov(fov)), fov, places=6)
        self.assertEqual(so.fov_for_scale(0.5), 180.0)
        self.assertEqual(so.scale_for_fov(200), 1.0)

    def test_fov_thresholds_keep_hysteresis(self):
        saved = dict(so.GLOBE_SETTINGS)
        try:
            so.configure_globe(map_enter_fov=10, globe_enter_fov=11)
            self.assertEqual(so.GLOBE_SETTINGS["map_enter_fov"], 10.0)
            self.assertEqual(so.GLOBE_SETTINGS["globe_enter_fov"], 15.0)
            so.configure_globe(map_enter_fov=8, globe_enter_fov=20)
            self.assertEqual(so.GLOBE_SETTINGS["globe_enter_fov"], 20.0)
        finally:
            so.GLOBE_SETTINGS.clear()
            so.GLOBE_SETTINGS.update(saved)

    def test_fov_settings_from_config(self):
        import configparser

        from cluster_visualization.src.config import Config

        cfg = Config.__new__(Config)
        cfg.config_parser = configparser.ConfigParser()
        cfg.config_parser.read_string("[view]\nmap_enter_fov = 5\nglobe_enter_fov = -1\n")
        got = cfg.get_globe_settings()
        self.assertEqual((got["map_enter_fov"], got["globe_enter_fov"]), (5.0, 15.0))

    def test_catalog_span(self):
        data = make_data(n=300)  # RA 50-54, Dec -30..-26
        span = so.catalog_span_deg(data)
        self.assertTrue(3.0 < span < 6.0, span)
        self.assertEqual(so.catalog_span_deg(data), span)  # cached

    @unittest.skipUnless(HAVE_HEALPY, "healpy not installed")
    def test_requested_view_goes_into_layout(self):
        fig, _ = so.build_sky_overview(make_data(n=200), TraceCreator(), {},
                                       view={"lon": 10.0, "lat": -20.0, "scale": 7.5}, uirevision="globe-X")
        proj = fig.layout.geo.projection
        self.assertEqual((proj.rotation.lon, proj.rotation.lat, proj.scale), (10.0, -20.0, 7.5))
        self.assertEqual(fig.layout.uirevision, "globe-X")
        self.assertEqual(fig.layout.meta["view"], {"lon": 10.0, "lat": -20.0, "scale": 7.5})


HANDOFF_HARNESS = r"""
const cases = JSON.parse(process.argv[process.argv.length - 1]);
const out = [];
for (const c of cases) {
    const calls = [];
    const gds = {};
    function gd(id, fl) { return {classList: {contains: () => true}, _fullLayout: fl}; }
    if (c.mapRanges) gds['cluster-plot'] = gd('cluster-plot', {xaxis: {range: c.mapRanges[0]}, yaxis: {range: c.mapRanges[1]}});
    if (c.globe) gds['sky-overview'] = gd('sky-overview', {geo: {projection: {rotation: {lon: c.globe.lon, lat: c.globe.lat}, scale: c.globe.scale}}});
    global.document = {getElementById: (id) => gds[id] || null};
    global.fetch = () => {};
    global.window = {
        _cvHandoffUntil: c.settling ? Date.now() + 10000 : 0,
        _cvLastRender: c.lastRender || null,
        Plotly: {Plots: {resize: () => {}}, relayout: (g, r) => calls.push(['relayout', r])},
        dash_clientside: {
            no_update: 'NU',
            callback_context: {triggered: [{prop_id: c.trigger}]},
            set_props: (id, p) => {
                calls.push([id, p]);
                if (id === 'cluster-plot' && gds['cluster-plot']) {
                    gds['cluster-plot']._fullLayout = {xaxis: {range: p.figure.layout.xaxis.range},
                                                       yaxis: {range: p.figure.layout.yaxis.range}};
                }
            },
        },
    };
    const f = eval('(' + HANDOFF + ')');
    const mapFig = c.noMap ? null : {data: [{}], layout: {xaxis: {range: c.figRanges ? c.figRanges[0] : undefined},
                                                          yaxis: {range: c.figRanges ? c.figRanges[1] : undefined}}};
    const globeFig = {data: [{}], layout: {geo: {projection: {rotation: {lon: 0, lat: 0}, scale: 1}}, meta: {}}};
    const res = f(null, c.mapRelayout || null, c.meta || {algorithm: 'PZWAV'}, 1, c.mode,
                  {map_enter_fov: 8, globe_enter_fov: 15}, mapFig, globeFig);
    out.push({res: res, calls: calls});
}
setTimeout(() => console.log(JSON.stringify(out)), 50);
"""


@unittest.skipUnless(__import__("shutil").which("node"), "node not installed")
class TestHandoffJS(unittest.TestCase):
    def run_cases(self, cases):
        import subprocess

        from cluster_visualization.callbacks.sky_overview_callbacks import HANDOFF_JS

        script = "const HANDOFF = " + json.dumps(HANDOFF_JS) + ";\n" + HANDOFF_HARNESS
        out = subprocess.run(["node", "-e", script, json.dumps(cases)], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def props(self, result, target):
        return [p for name, p in (c for c in result["calls"] if c[0] != "relayout") if name == target]

    def test_globe_zoom_in_hands_over_to_map(self):
        (r,) = self.run_cases([{"mode": "globe", "trigger": "sky-overview.relayoutData",
                                "globe": {"lon": -52.0, "lat": -28.0, "scale": 20.0},
                                "mapRanges": [[60, 40], [-35, -20]]}])
        self.assertEqual(r["res"], "plotly")
        fig = self.props(r, "cluster-plot")[0]["figure"]
        xr, yr = fig["layout"]["xaxis"]["range"], fig["layout"]["yaxis"]["range"]
        self.assertGreater(xr[0], xr[1])  # RA axis reversed
        self.assertAlmostEqual((xr[0] + xr[1]) / 2, 52.0, places=6)
        self.assertAlmostEqual((yr[0] + yr[1]) / 2, -28.0, places=6)
        self.assertAlmostEqual(yr[1] - yr[0], so.fov_for_scale(20.0), places=6)
        self.assertTrue(fig["layout"]["uirevision"].startswith("handoff-"))
        # The new ranges are replayed as a relayout for the viewport tracker
        self.assertTrue(any(c[0] == "relayout" for c in r["calls"]))

    def test_globe_wide_stays_globe(self):
        (r,) = self.run_cases([{"mode": "globe", "trigger": "sky-overview.relayoutData",
                                "globe": {"lon": -52.0, "lat": -28.0, "scale": 5.0}}])
        self.assertEqual(r["res"], "NU")

    def test_map_zoom_out_hands_back_with_hysteresis(self):
        wide, mid = self.run_cases([
            {"mode": "plotly", "trigger": "cluster-plot.relayoutData", "mapRanges": [[70, 40], [-40, -18]]},
            {"mode": "plotly", "trigger": "cluster-plot.relayoutData", "mapRanges": [[57, 47], [-33, -23]]},
        ])
        self.assertEqual(wide["res"], "globe")
        req = self.props(wide, "globe-request")[0]["data"]
        self.assertAlmostEqual(req["lon"], -55.0, places=6)
        self.assertAlmostEqual(req["lat"], -29.0, places=6)
        # span = max(dRA cos(dec), dDec) = max(30 cos 29deg, 22)
        self.assertAlmostEqual(so.fov_for_scale(req["scale"]), 30 * math.cos(math.radians(29)), places=6)
        self.assertEqual(req["uirevision"], "globe-PZWAV")
        proj = self.props(wide, "sky-overview")[0]["figure"]["layout"]["geo"]["projection"]
        self.assertAlmostEqual(proj["scale"], req["scale"])
        self.assertEqual(mid["res"], "NU")  # 10 deg: between 8 and 15

    def test_ra_wrap(self):
        (r,) = self.run_cases([{"mode": "plotly", "trigger": "cluster-plot.relayoutData",
                                "mapRanges": [[369, 349], [-5, 15]]}])
        req = self.props(r, "globe-request")[0]["data"]
        self.assertAlmostEqual(req["lon"], 1.0, places=6)  # RA 359 -> lon +1

    def test_guards(self):
        settling, aladin, nomap = self.run_cases([
            {"mode": "globe", "trigger": "sky-overview.relayoutData", "settling": True,
             "globe": {"lon": 0, "lat": 0, "scale": 50}, "mapRanges": [[1, 0], [0, 1]]},
            {"mode": "aladin", "trigger": "cluster-plot.relayoutData", "mapRanges": [[90, 0], [-40, 40]]},
            {"mode": "globe", "trigger": "sky-overview.relayoutData", "noMap": True,
             "globe": {"lon": 0, "lat": 0, "scale": 50}},
        ])
        for r in (settling, aladin, nomap):
            self.assertEqual(r["res"], "NU")
            self.assertEqual(r["calls"], [])

    def test_render_starting_view(self):
        wide, narrow, zoomed, seen = self.run_cases([
            {"mode": "plotly", "trigger": "rendered-meta-store.data",
             "meta": {"algorithm": "PZWAV", "rendered_at": 1, "span": 40}},
            {"mode": "globe", "trigger": "rendered-meta-store.data",
             "meta": {"algorithm": "PZWAV", "rendered_at": 2, "span": 4}},
            {"mode": "plotly", "trigger": "rendered-meta-store.data",
             "meta": {"algorithm": "PZWAV", "rendered_at": 3, "span": 40}, "figRanges": [[55, 50], [-30, -25]]},
            {"mode": "plotly", "trigger": "rendered-meta-store.data", "lastRender": 4,
             "meta": {"algorithm": "PZWAV", "rendered_at": 4, "span": 40}},
        ])
        self.assertEqual(wide["res"], "globe")
        self.assertTrue(self.props(wide, "globe-request")[0]["data"]["fit"])
        self.assertEqual(narrow["res"], "plotly")
        self.assertEqual(zoomed["res"], "NU")  # kept zoom of 5 deg: stay on the map
        self.assertEqual(seen["res"], "NU")  # patch updates of the same render

    def test_globe_button_uses_map_view(self):
        (r,) = self.run_cases([{"mode": "plotly", "trigger": "view-mode-globe-btn.n_clicks",
                                "mapRanges": [[54, 50], [-30, -26]]}])
        self.assertEqual(r["res"], "globe")
        req = self.props(r, "globe-request")[0]["data"]
        self.assertAlmostEqual(req["lon"], -52.0, places=6)
        self.assertAlmostEqual(so.fov_for_scale(req["scale"]), 15.0, places=6)
