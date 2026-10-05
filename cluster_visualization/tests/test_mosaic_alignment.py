"""Whole-tile MER mosaic placement: sources land where the WCS puts them.

The tile image is a PNG in ``layout.images`` stretched over an RA/Dec box. A
gnomonic tile is not a rectangle in RA/Dec, so the image has to be resampled
onto a regular RA/Dec grid; stretching the raw pixels misplaces corner sources
by about 10 arcsec at Dec -50.
"""

import base64
import unittest
from io import BytesIO
from unittest import mock

import numpy as np
from astropy import wcs
from PIL import Image

from cluster_visualization.src.mermosaic import MOSAICHandler

N = 4000
CDELT = 32.0 / 60.0 / N  # 32 arcmin tile, like MER
SCALE = 0.25  # output pixel = 4 input pixels (~1.9 arcsec)


def _handler():
    handler = MOSAICHandler.__new__(MOSAICHandler)
    handler.default_mosaic_provider = "local_fits"
    handler.img_scale_factor = SCALE
    handler.img_width = handler.img_height = int(N * SCALE)
    handler.max_pixels_for_stats = 10_000_000
    return handler


def _tile():
    w = wcs.WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.cd = [[-CDELT, 0.0], [0.0, CDELT]]
    w.wcs.crpix = [N / 2 + 0.5, N / 2 + 0.5]
    w.wcs.crval = [46.55, -50.30]
    w.pixel_shape = (N, N)

    m = 60
    stars = [(N // 2, N // 2), (m, m), (N - m, m), (m, N - m), (N - m, N - m),
             (N // 2, m), (N // 2, N - m), (m, N // 2), (N - m, N // 2)]
    data = np.random.default_rng(0).normal(0.0, 1.0, (N, N)).astype(np.float32)
    yy, xx = np.mgrid[-12:13, -12:13]
    blob = 1e4 * np.exp(-(xx**2 + yy**2) / (2 * 4.0**2))
    for x, y in stars:
        data[y - 12:y + 13, x - 12:x + 13] += blob
    return w, data, stars


class TestMosaicTileAlignment(unittest.TestCase):
    def setUp(self):
        self.wcs, self.data, self.stars = _tile()
        handler = _handler()
        info = {"data": self.data, "wcs": self.wcs, "header": self.wcs.to_header()}
        with mock.patch.object(handler, "get_mosaic_fits_data_by_mertile", return_value=info):
            self.img = handler.create_mosaic_image_trace(1, provider="local_fits")
        png = base64.b64decode(self.img["source"].split(",", 1)[1])
        self.pixels = np.asarray(Image.open(BytesIO(png)).convert("LA"), dtype=float)

    def _shown_position(self, ra, dec):
        """Centroid of the source nearest (ra, dec) in the PNG, as RA/Dec."""
        img = self.img
        h, w = self.pixels.shape[:2]
        dra, ddec = img["sizex"] / w, img["sizey"] / h
        # layout.images anchored top-left at (x=ra_max, y=dec_max)
        c = int((img["x"] - ra) / dra)
        r = int((img["y"] - dec) / ddec)
        win = 20
        r0, c0 = max(r - win, 0), max(c - win, 0)
        patch = self.pixels[r0:r + win, c0:c + win, 0]
        patch = patch - np.median(patch)  # background sits mid-grey after the stretch
        weights = np.where(patch > 0.5 * patch.max(), patch, 0.0)
        rows, cols = np.indices(patch.shape)
        rc = (weights * rows).sum() / weights.sum() + r0
        cc = (weights * cols).sum() / weights.sum() + c0
        return img["x"] - (cc + 0.5) * dra, img["y"] - (rc + 0.5) * ddec

    def test_sources_placed_by_wcs(self):
        tolerance = 1.0 * CDELT / SCALE * 3600  # one output pixel, arcsec
        for x, y in self.stars:
            ra, dec = self.wcs.wcs_pix2world(x, y, 0)
            shown_ra, shown_dec = self._shown_position(float(ra), float(dec))
            off = np.hypot((shown_ra - ra) * np.cos(np.radians(dec)), shown_dec - dec) * 3600
            self.assertLess(off, tolerance, f"source at pixel ({x}, {y}) off by {off:.2f} arcsec")

    def test_outside_footprint_transparent(self):
        alpha = self.pixels[..., 1]
        self.assertEqual(alpha[alpha.shape[0] // 2, alpha.shape[1] // 2], 255)
        # A TAN tile at Dec -50 is a trapezoid in RA/Dec: some box corners lie outside it
        corners = [alpha[0, 0], alpha[0, -1], alpha[-1, 0], alpha[-1, -1]]
        self.assertIn(0, corners)


if __name__ == "__main__":
    unittest.main()
