"""Cluster modal HEALPix mask cutout uses the sidebar viewport-mask mechanism.

The cutout is the viewport mask built over a size x size arcmin box around the
cluster, with trace names prefixed by CUTOUT_MASK_PREFIX so it is a separate layer.
"""

import unittest
from unittest import mock

import healpy as hp
import numpy as np

from cluster_visualization.src.mermosaic import MOSAICHandler
from cluster_visualization.src.visualization.trace_registry import (
    CUTOUT_MASK_PREFIX,
    TraceRegistry,
    TraceType,
)

RA, DEC = 46.67885, -50.38921
SIZE_ARCMIN = 4.0


def _handler():
    handler = MOSAICHandler.__new__(MOSAICHandler)
    handler.default_mosaic_provider = "local_fits"
    return handler


def _footprint(*args, mask_type="corrected", mertileid=None, binary_inverted=False):
    """A few nside-16384 NESTED pixels at the cluster; zero weight when inverted."""
    pixels = hp.ang2pix(16384, RA + np.arange(5) * 1e-3, np.full(5, DEC), nest=True, lonlat=True)
    weights = np.zeros(5, np.float32) if binary_inverted else np.linspace(0.9, 1.0, 5).astype(np.float32)
    return np.asarray(pixels, np.int64), weights


class TestMaskCutout(unittest.TestCase):
    def setUp(self):
        self.handler = _handler()
        patches = [
            mock.patch.object(self.handler, "_get_mask_footprint_in_viewport", side_effect=_footprint),
            # The cutout must not load the MER mosaic FITS any more
            mock.patch.object(self.handler, "get_mosaic_cutout", side_effect=AssertionError("FITS load")),
            mock.patch.object(
                self.handler, "get_mosaic_fits_data_by_mertile", side_effect=AssertionError("FITS load")
            ),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.footprint = self.handler._get_mask_footprint_in_viewport

    def _cutout(self, **kwargs):
        clickdata = {"cluster_ra": RA, "cluster_dec": DEC, "mask_cutout_size": SIZE_ARCMIN}
        return self.handler.create_mask_overlay_cutout_trace({}, clickdata, opacity=0.3, **kwargs)

    def test_box_around_cluster(self):
        self._cutout()
        ra_min, ra_max, dec_min, dec_max = self.footprint.call_args.args[:4]
        half = SIZE_ARCMIN / 120.0
        self.assertAlmostEqual(dec_min, DEC - half)
        self.assertAlmostEqual(dec_max, DEC + half)
        self.assertAlmostEqual(ra_max - ra_min, 2 * half / np.cos(np.radians(DEC)))
        self.assertAlmostEqual((ra_min + ra_max) / 2, RA)
        self.assertEqual(self.footprint.call_args.kwargs["mask_type"], "corrected")

    def test_cutout_names_and_layer(self):
        traces = self._cutout()
        names = [t.name for t in traces]
        self.assertTrue(names)
        self.assertTrue(all(n.startswith(CUTOUT_MASK_PREFIX) for n in names), names)
        self.assertIn("Cutout Mask aladin moc", names)
        self.assertIn("Cutout Mask Colorbar", names)
        self.assertTrue(any(n.startswith("Cutout Mask overlay bin") for n in names))
        for trace in traces:
            self.assertEqual(TraceRegistry.classify_trace(trace), TraceType.MASK_OVERLAY, trace.name)
        # Same look as the sidebar mask: white alpha fill
        fills = [t.fillcolor for t in traces if t.name.startswith("Cutout Mask overlay")]
        self.assertTrue(all(f.startswith("rgba(255,255,255,") for f in fills), fills)

    def test_inverted_passed_through(self):
        traces = self._cutout(binary_inverted=True)
        self.assertTrue(self.footprint.call_args.kwargs["binary_inverted"])
        names = [t.name for t in traces]
        self.assertTrue(any(n.startswith("Cutout Inverted mask overlay") for n in names), names)
        self.assertIn("Cutout Inverted mask aladin moc", names)

    def test_effcov_per_tile_keeps_prefix(self):
        with mock.patch.object(self.handler, "_find_intersecting_tiles", return_value=[101, 102]), \
                mock.patch.object(self.handler, "_extract_tile_bounds",
                                  return_value=(RA - 0.3, RA + 0.3, DEC - 0.3, DEC + 0.3)):
            traces = self._cutout(mask_type="effcov")
        tile_calls = [c.kwargs.get("mertileid") for c in self.footprint.call_args_list]
        self.assertEqual(tile_calls, [101, 102])
        self.assertTrue(traces)
        self.assertTrue(all(t.name.startswith(CUTOUT_MASK_PREFIX) for t in traces))

    def test_viewport_mask_names_unchanged(self):
        relayout = {
            "xaxis.range[0]": RA + 0.05, "xaxis.range[1]": RA - 0.05,
            "yaxis.range[0]": DEC - 0.05, "yaxis.range[1]": DEC + 0.05,
        }
        traces = self.handler.load_mask_overlay_traces_in_zoom({}, relayout, opacity=0.7)
        names = [t.name for t in traces]
        self.assertIn("Mask aladin moc", names)
        self.assertIn("Mask Colorbar", names)
        self.assertFalse(any(n.startswith(CUTOUT_MASK_PREFIX) for n in names))


if __name__ == "__main__":
    unittest.main()
