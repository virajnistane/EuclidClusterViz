"""'Only clusters with a match in' galaxy catalogs: the filter, the status count, the
sidebar control and the dropdown options."""

import os
import tempfile
import unittest

import dash
import numpy as np
from astropy.io import fits
from loguru import logger

from cluster_visualization.callbacks.catalog_callbacks import CatalogCallbacks
from cluster_visualization.callbacks.main_plot import MainPlotCallbacks
from cluster_visualization.src.data.catalog_registry import CatalogRegistry
from cluster_visualization.src.data.galaxy_catalog import CatalogSpec
from cluster_visualization.src.visualization.traces import TraceCreator
from cluster_visualization.ui.layout import AppLayout
from cluster_visualization.ui.sidebar_sections import NO_FILTER_CATALOG_HELP, SidebarSections

NED_IDS = [5, 259, 338]


def _ned_fits(directory):
    rows = np.zeros(5, dtype=[("ID_UNIQUE_CLUSTER", ">i8"), ("RA", ">f8"), ("DEC", ">f8")])
    rows["ID_UNIQUE_CLUSTER"] = [5, 5, 259, 338, 338]  # several galaxies per cluster
    rows["RA"] = np.linspace(33.7, 33.9, 5)
    rows["DEC"] = -52.2
    path = os.path.join(directory, "ned.fits")
    fits.BinTableHDU(rows).writeto(path)
    return path


def _merged(n=1000):
    merged = np.zeros(
        n, dtype=[("ID_UNIQUE_CLUSTER", "i8"), ("Z_CLUSTER", "f8"), ("SNR_CLUSTER", "f8")]
    )
    merged["ID_UNIQUE_CLUSTER"] = np.arange(n)
    merged["Z_CLUSTER"] = 0.5
    merged["SNR_CLUSTER"] = 10.0
    return merged


def _kwargs(catalog_ids):
    return MainPlotCallbacks._resolve_filter_kwargs(
        None,
        None,
        True,
        True,
        None,
        True,
        None,
        None,
        True,
        True,
        None,
        None,
        None,
        None,
        None,
        catalog_filter_ids=catalog_ids,
    )


class CatalogFilterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        self.ned = _ned_fits(self.tmp.name)
        self.cid = self.registry.add(
            CatalogSpec(
                "NED spec-z",
                self.ned,
                {"RA": "RA", "DEC": "DEC", "CLUSTER_ID": "ID_UNIQUE_CLUSTER"},
            )
        )
        self.data = {
            "data_detcluster_mergedcat": _merged(),
            "paths": {"use_gluematchcat": True},
            "algorithm": "PZWAV",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _selected(self, catalog_ids):
        creator = TraceCreator(catalog_registry=self.registry)
        return creator.selected_clusters(self.data, **_kwargs(catalog_ids))

    def test_filter_keeps_clusters_in_the_catalog(self):
        self.assertEqual(_kwargs(None)["catalog_filter_ids"], [])
        self.assertEqual(len(self._selected(None)), 1000)
        self.assertEqual(len(self._selected([])), 1000)
        self.assertEqual(sorted(self._selected([self.cid])["ID_UNIQUE_CLUSTER"]), NED_IDS)

    def test_union_of_catalogs(self):
        other = os.path.join(self.tmp.name, "other.csv")
        with open(other, "w") as f:
            f.write("ra,dec,cluster_id\n10,0,7\n10,0,5\n")
        oid = self.registry.add(
            CatalogSpec("Other", other, {"RA": "ra", "DEC": "dec", "CLUSTER_ID": "cluster_id"})
        )
        selected = self._selected([self.cid, oid])
        self.assertEqual(sorted(selected["ID_UNIQUE_CLUSTER"]), [5, 7, 259, 338])

    def test_unloadable_catalog_is_skipped_and_said(self):
        gone = self.registry.add(
            CatalogSpec(
                "Gone",
                os.path.join(self.tmp.name, "gone.fits"),
                {"RA": "a", "DEC": "b", "CLUSTER_ID": "c"},
            )
        )
        messages = []
        sink = logger.add(messages.append, level="WARNING", format="{message}")
        try:
            rows = self._selected([gone])
            both = self._selected([gone, self.cid])
        finally:
            logger.remove(sink)
        self.assertEqual(len(rows), 1000)  # nothing usable: not applied
        self.assertEqual(sorted(both["ID_UNIQUE_CLUSTER"]), NED_IDS)
        self.assertTrue(any("skipping 'gone'" in str(m) for m in messages), messages)

    def test_without_a_match(self):
        kwargs = dict(_kwargs([self.cid]), catalog_filter_mode="without")
        selected = TraceCreator(catalog_registry=self.registry).selected_clusters(
            self.data, **kwargs
        )
        self.assertEqual(len(selected), 1000 - len(NED_IDS))
        self.assertFalse(set(NED_IDS) & set(selected["ID_UNIQUE_CLUSTER"]))
        self.assertEqual(_kwargs([self.cid])["catalog_filter_mode"], "with")  # default

    def test_status_count_follows_filter(self):
        callbacks = MainPlotCallbacks.__new__(MainPlotCallbacks)
        callbacks.trace_creator = TraceCreator(catalog_registry=self.registry)
        self.assertEqual(callbacks._count_selected(self.data, _kwargs([self.cid]), fallback=999), 3)
        self.assertEqual(callbacks._count_selected(self.data, _kwargs([]), fallback=999), 1000)


class CatalogFilterControlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        app = dash.Dash(__name__)
        app.layout = AppLayout.create_layout()
        CatalogCallbacks(app, self.registry)
        fn = next(
            v["callback"]
            for k, v in app.callback_map.items()
            if "catalog-filter-dropdown.options" in k
        )
        self.options = getattr(fn, "__wrapped__", fn)

    def tearDown(self):
        self.tmp.cleanup()

    def test_section_starts_disabled(self):
        section = SidebarSections.create_catalog_filter_section()
        dropdown = section.children[1]
        self.assertEqual(
            (dropdown.id, dropdown.disabled, dropdown.value), ("catalog-filter-dropdown", True, [])
        )
        mode = section.children[3]
        self.assertEqual((mode.id, mode.value), ("catalog-filter-mode", "with"))
        self.assertEqual(section.children[-1].children.children, NO_FILTER_CATALOG_HELP)

    def test_options_follow_the_catalog_list(self):
        self.assertEqual(self.options(0, []), ([], [], True, NO_FILTER_CATALOG_HELP))
        ned = _ned_fits(self.tmp.name)
        cid = self.registry.add(
            CatalogSpec(
                "NED spec-z", ned, {"RA": "RA", "DEC": "DEC", "CLUSTER_ID": "ID_UNIQUE_CLUSTER"}
            )
        )
        self.registry.add(
            CatalogSpec("No clusters", ned, {"RA": "RA", "DEC": "DEC"})
        )  # not offered
        options, value, disabled, _ = self.options(1, [])
        self.assertEqual(options, [{"label": "NED spec-z (3 clusters)", "value": cid}])
        self.assertIs(value, dash.no_update)
        self.assertFalse(disabled)
        # A chosen catalog that stops qualifying is dropped from the choice
        self.registry.remove(cid)
        options, value, disabled, _ = self.options(2, [cid])
        self.assertEqual((options, value, disabled), ([], [], True))


if __name__ == "__main__":
    unittest.main()
