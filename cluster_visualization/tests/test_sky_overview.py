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
        self.assertEqual(cfg.get_globe_settings(), {"nside_max": 512, "globe_max_cells": 3000})

        saved = dict(so.GLOBE_SETTINGS)
        try:
            so.configure_globe(nside_max=1000, globe_max_cells=50)
            self.assertEqual(so.GLOBE_SETTINGS, {"nside_max": 1024, "globe_max_cells": 100})
        finally:
            so.GLOBE_SETTINGS.update(saved)


if __name__ == "__main__":
    unittest.main()
