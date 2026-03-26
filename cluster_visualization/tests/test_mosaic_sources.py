"""Tests for mosaic provider selection and ESA source discovery."""

import os
import sys
import unittest
from unittest.mock import patch

# Add source directory for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cluster_visualization.src.mermosaic import MOSAICHandler


class TestMosaicSourceProviders(unittest.TestCase):
    """Unit tests for provider routing and source discovery helpers."""

    def setUp(self):
        # Bypass __init__ to avoid filesystem-dependent loader setup.
        self.handler = MOSAICHandler.__new__(MOSAICHandler)
        self.handler.default_mosaic_provider = "local_fits"
        self.handler.default_esa_source = "CDS/P/DSS2/color"
        self.handler.esa_source_discovery_url = "https://example.invalid/moc"
        self.handler.esa_timeout_seconds = 1
        self.handler.esa_source_cache_ttl_seconds = 3600
        self.handler._cached_esa_sources = None
        self.handler._cached_esa_sources_ts = None
        self.handler.traces_cache = {}
        self.handler.FALLBACK_ESA_SOURCES = [
            {
                "id": "CDS/P/DSS2/color",
                "label": "DSS2 Color",
                "attribution": "DSS2 / CDS",
            }
        ]

    def test_normalize_provider_aliases(self):
        self.assertEqual(self.handler._normalize_provider("fits"), "local_fits")
        self.assertEqual(self.handler._normalize_provider("MER"), "local_fits")
        self.assertEqual(self.handler._normalize_provider("esa"), "esa_sky")
        self.assertEqual(self.handler._normalize_provider("ESA_SKY"), "esa_sky")

    def test_discover_esa_sources_fallback_on_failure(self):
        with patch("cluster_visualization.src.mermosaic.urlopen", side_effect=RuntimeError("network down")):
            sources = self.handler._discover_esa_sources()

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], "CDS/P/DSS2/color")

    def test_get_available_mosaic_sources_local(self):
        sources = self.handler.get_available_mosaic_sources(provider="local_fits")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], "local_mer")

    def test_provider_route_uses_provider_specific_loader(self):
        with patch.object(
            self.handler,
            "_load_local_mosaic_fits_data",
            return_value={"data": [[1.0]], "wcs": None, "header": None},
        ) as local_loader, patch.object(
            self.handler,
            "_load_esa_cutout_by_mertile",
            return_value={"data": [[0.5]], "wcs": None, "header": None},
        ) as esa_loader:
            local_result = self.handler._load_mosaic_data_by_provider(1001, provider="local_fits")
            esa_result = self.handler._load_mosaic_data_by_provider(
                1001,
                provider="esa_sky",
                source_id="CDS/P/DSS2/color",
                tile_bounds=(10.0, 11.0, -1.0, 0.0),
            )

        self.assertIsNotNone(local_result)
        self.assertIsNotNone(esa_result)
        local_loader.assert_called_once()
        esa_loader.assert_called_once()

    def test_mask_overlay_loader_passes_provider_and_source(self):
        relayout_data = {
            "xaxis.range[0]": 10.0,
            "xaxis.range[1]": 11.0,
            "yaxis.range[0]": -1.0,
            "yaxis.range[1]": 0.0,
        }

        with patch.object(
            self.handler,
            "_extract_zoom_ranges",
            return_value=(10.0, 11.0, -1.0, 0.0),
        ), patch.object(
            self.handler,
            "_find_intersecting_tiles",
            return_value=[1001],
        ), patch.object(
            self.handler,
            "_extract_tile_bounds",
            return_value=(10.0, 11.0, -1.0, 0.0),
        ), patch.object(
            self.handler,
            "create_mask_overlay_trace",
            return_value=[],
        ) as mask_trace_creator:
            self.handler.load_mask_overlay_traces_in_zoom(
                data={},
                relayout_data=relayout_data,
                provider="esa_sky",
                source_id="CDS/P/DSS2/color",
            )

        _, kwargs = mask_trace_creator.call_args
        self.assertEqual(kwargs["provider"], "esa_sky")
        self.assertEqual(kwargs["source_id"], "CDS/P/DSS2/color")


if __name__ == "__main__":
    unittest.main()
