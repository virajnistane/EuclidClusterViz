"""Parquet catalog caches (SCALING #9) and the shared members cache (SCALING #11)."""

import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from astropy.io import fits

from cluster_visualization.src.data import loader as loader_mod
from cluster_visualization.src.data.loader import MEMBER_COLUMNS, DataLoader
from cluster_visualization.utils import columnar
from cluster_visualization.utils.disk_cache import DiskCache


def _write_xml(path, element, filename):
    with open(path, "w") as f:
        f.write(
            f"<root><Data><{element}><DataContainer><FileName>{filename}</FileName>"
            f"</DataContainer></{element}></Data></root>"
        )


def _loader(cache_dir):
    loader = DataLoader(config=None, use_disk_cache=False)
    loader.use_disk_cache = True
    loader.disk_cache = DiskCache(cache_dir)
    return loader


@unittest.skipUnless(columnar.HAVE_ARROW, "pyarrow not installed")
class TestColumnar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "t.parquet")
        dt = np.dtype(
            [("A", ">f8"), ("B", ">i8"), ("S", "S16"), ("L", "?"), ("V", ">f4", (3,))]
        )
        self.arr = np.zeros(4, dt)
        self.arr["A"] = [1.0, np.nan, 3.0, 4.0]
        self.arr["B"] = [5, 6, 7, 2**40]
        self.arr["S"] = [b"x", b"yy", b"", b"abcdefghijklmnop"]
        self.arr["L"] = [True, False, True, False]
        self.arr["V"] = np.arange(12).reshape(4, 3)

    def test_round_trip(self):
        columnar.write_structured(self.path, self.arr, {"snr": [1.5, None]})
        out, meta = columnar.read_structured(self.path)
        self.assertEqual(out.dtype.names, self.arr.dtype.names)
        for name in self.arr.dtype.names:
            np.testing.assert_array_equal(out[name], self.arr[name])
        self.assertEqual(meta, {"snr": [1.5, None]})
        self.assertTrue(out.dtype["A"].isnative)
        self.assertEqual(out[0].B, 5)  # record rows, like np.array(FITS_rec)

    def test_column_subset(self):
        columnar.write_structured(self.path, self.arr)
        out, _ = columnar.read_structured(self.path, ["V", "A", "missing"])
        self.assertEqual(out.dtype.names, ("A", "V"))
        np.testing.assert_array_equal(out["V"], self.arr["V"])

    def test_object_column_refused(self):
        arr = np.array([(1,)], dtype=[("O", "O")])
        with self.assertRaises(TypeError):
            columnar.write_structured(self.path, arr)
        cache = DiskCache(self.tmp)
        self.assertFalse(cache.set_table("obj", arr))
        self.assertIsNone(cache.get_table("obj"))

    def test_cache_listing_and_clear(self):
        cache = DiskCache(self.tmp)
        self.assertTrue(cache.set_table("k", self.arr, None, {"x": 1}))
        cache.set("p", {"a": 1})
        self.assertEqual(cache.get_cache_info()["num_entries"], 2)
        cache.clear("k")
        self.assertIsNone(cache.get_table("k"))
        self.assertEqual(cache.get("p"), {"a": 1})


class TestMergedCatalogCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "data"))
        rows = np.zeros(4, dtype=[("SNR_CLUSTER", ">f4"), ("DET_CODE_NB", ">i4"), ("Z", ">f8")])
        rows["SNR_CLUSTER"] = [3, 4, 5, 6]
        rows["DET_CODE_NB"] = [2, 2, 1, 1]
        rows["Z"] = [0.1, 0.2, 0.3, 0.4]
        fits.BinTableHDU(rows).writeto(os.path.join(self.tmp, "data", "cat.fits"))
        xml = os.path.join(self.tmp, "cat.xml")
        _write_xml(xml, "FullDetectionsFile", "cat.fits")
        self.paths = {"use_gluematchcat": True, "gluematchcat_clusters_xml": xml,
                      "gluematchcat_dir": self.tmp}
        self.cache_dir = os.path.join(self.tmp, "cache")

    def _load(self):
        return _loader(self.cache_dir)._load_data_detcluster_mergedcat_with_minmax_snr(
            self.paths, "BOTH"
        )

    @unittest.skipUnless(columnar.HAVE_ARROW, "pyarrow not installed")
    def test_second_load_hits_parquet(self):
        first = self._load()
        self.assertTrue(any(f.endswith(".parquet") for f in os.listdir(self.cache_dir)))
        with mock.patch.object(loader_mod.fits, "open", side_effect=AssertionError("FITS read")):
            second = self._load()
        self.assertEqual(second[1:], first[1:])
        self.assertEqual(second[1:], (3.0, 4.0, 5.0, 6.0))
        np.testing.assert_array_equal(second[0]["Z"], first[0]["Z"])

    def test_without_arrow_uses_pickle(self):
        with mock.patch.object(columnar, "HAVE_ARROW", False):
            first = self._load()
            self.assertFalse(any(f.endswith(".parquet") for f in os.listdir(self.cache_dir)))
            with mock.patch.object(loader_mod.fits, "open", side_effect=AssertionError("FITS read")):
                second = self._load()
        self.assertEqual(second[1:], first[1:])


@unittest.skipUnless(columnar.HAVE_ARROW, "pyarrow not installed")
class TestTileTables(unittest.TestCase):
    def test_round_trip_two_layouts(self):
        pz = np.zeros(3, dtype=[("RA", ">f8"), ("SNR_CLUSTER", ">f4")])
        pz["RA"] = [1, 2, 3]
        am = np.zeros(2, dtype=[("RA", ">f8"), ("SNR_CLUSTER", ">f4"), ("LAMBDA", ">f4")])
        am["LAMBDA"] = [7, 8]
        tiles = {
            "1_PZWAV": {"tile_id": 1, "algorithm": "PZWAV", "detfits_data": pz, "detxml_file": "a"},
            "2_PZWAV": {"tile_id": 2, "algorithm": "PZWAV", "detfits_data": pz[:0]},
            "1_AMICO": {"tile_id": 1, "algorithm": "AMICO", "detfits_data": am},
        }
        loader = _loader(tempfile.mkdtemp())
        self.assertTrue(loader._set_tile_tables("BOTH", tiles, []))
        out = loader._get_tile_tables("BOTH", [])
        self.assertEqual(list(out), list(tiles))
        for key, tile in tiles.items():
            self.assertEqual(out[key]["tile_id"], tile["tile_id"])
            self.assertEqual(out[key]["algorithm"], tile["algorithm"])
            self.assertEqual(out[key]["detfits_data"].dtype.names, tile["detfits_data"].dtype.names)
            for name in tile["detfits_data"].dtype.names:
                np.testing.assert_array_equal(out[key]["detfits_data"][name], tile["detfits_data"][name])
        self.assertEqual(out["1_PZWAV"]["detxml_file"], "a")


class TestMembersCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "data"))
        rng = np.random.default_rng(1)
        n = 200
        rows = np.zeros(n, dtype=[("ID_UNIQUE_CLUSTER", ">i8"), ("OBJECT_ID", ">i8"),
                                   ("PMEM_ZP", ">f4"), ("PMEM_RS", ">f4"), ("EXTRA", ">f8", (4,))])
        rows["ID_UNIQUE_CLUSTER"] = rng.integers(0, 20, n)
        rows["OBJECT_ID"] = np.arange(n)
        rows["PMEM_ZP"] = rng.random(n)
        self.rows = rows
        fits.BinTableHDU(rows).writeto(os.path.join(self.tmp, "data", "mem.fits"))
        xml = os.path.join(self.tmp, "mem.xml")
        _write_xml(xml, "RichMembersFile", "mem.fits")
        self.data = {"paths": {"gluematchcat_members_xml": xml, "gluematchcat_dir": self.tmp},
                     "data_gluematchcat_members": None}
        self.cache_dir = os.path.join(self.tmp, "cache")

    def _expected(self, cid):
        return np.sort(self.rows["OBJECT_ID"][self.rows["ID_UNIQUE_CLUSTER"] == cid])

    def test_pruned_sorted_and_lookup(self):
        loader = _loader(self.cache_dir)
        members = loader.get_gluematchcat_members(self.data)
        self.assertEqual(members.dtype.names, MEMBER_COLUMNS)
        self.assertTrue(np.all(np.diff(members["ID_UNIQUE_CLUSTER"]) >= 0))
        for cid in (0, 5, 19, 99):
            got = loader.members_for_cluster(members, cid)
            np.testing.assert_array_equal(np.sort(got["OBJECT_ID"]), self._expected(cid))
            self.assertTrue(np.all(got["ID_UNIQUE_CLUSTER"] == cid))

    def test_shared_across_algorithms_one_fits_read(self):
        loader = _loader(self.cache_dir)
        other = dict(self.data)  # a second algorithm's data dict, same paths
        real_open = fits.open
        with mock.patch.object(loader_mod.fits, "open", side_effect=real_open) as opened:
            a = loader.get_gluematchcat_members(self.data)
            b = loader.get_gluematchcat_members(other)
        self.assertIs(a, b)
        self.assertEqual(opened.call_count, 1)

    def test_new_loader_uses_disk_cache(self):
        _loader(self.cache_dir).get_gluematchcat_members(self.data)
        with mock.patch.object(loader_mod.fits, "open", side_effect=AssertionError("FITS read")):
            members = _loader(self.cache_dir).get_gluematchcat_members(self.data)
        loader = _loader(self.cache_dir)
        self.assertEqual(len(members), len(self.rows))
        np.testing.assert_array_equal(
            np.sort(loader.members_for_cluster(members, 5)["OBJECT_ID"]), self._expected(5)
        )

    def test_injected_array_uses_mask(self):
        loader = _loader(self.cache_dir)
        unsorted = np.array(self.rows)
        got = loader.members_for_cluster(unsorted, 5)
        np.testing.assert_array_equal(np.sort(got["OBJECT_ID"]), self._expected(5))

    def test_not_configured(self):
        loader = _loader(self.cache_dir)
        self.assertIsNone(loader.get_gluematchcat_members({"paths": {}}))


if __name__ == "__main__":
    unittest.main()
