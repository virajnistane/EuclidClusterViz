"""Generic galaxy catalogs: column inspection, mapping suggestions, validation,
loading (selection, standard names, cache) and the per-user registry."""

import os
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.table import Table

from cluster_visualization.src.data import galaxy_catalog as gc
from cluster_visualization.src.data.catalog_registry import CatalogRegistry
from cluster_visualization.src.data.galaxy_catalog import (
    CatalogSpec,
    GalaxyCatalog,
    find_table,
    inspect_columns,
    suggest_mapping,
    suggest_select_column,
    validate_mapping,
)


def _ned_fits(directory, n=6):
    """NED-like layout: upper-case names, cluster IDs, string flags."""
    rows = np.zeros(
        n,
        dtype=[
            ("ID_UNIQUE_CLUSTER", ">i8"),
            ("Z_CLUSTER", ">f4"),
            ("RA", ">f8"),
            ("DEC", ">f8"),
            ("Z", ">f8"),
            ("ZUNC", ">f8"),
            ("ZFLAG", "S3"),
            ("ZREF", "S19"),
            ("R_MPC", ">f8"),
        ],
    )
    rows["ID_UNIQUE_CLUSTER"] = [5, 5, 259, 338, 338, 338]
    rows["RA"] = np.linspace(33.7, 33.9, n)
    rows["DEC"] = np.linspace(-52.3, -52.1, n)
    rows["Z"] = 0.48
    rows["ZFLAG"] = b"SLS"
    path = os.path.join(directory, "ned.fits")
    fits.BinTableHDU(rows).writeto(path)
    return path


def _euclid_fits(directory, n=8):
    """Euclid-like layout: lower-case names, OBJECT_ID, a boolean selection, an array column."""
    rows = np.zeros(
        n,
        dtype=[
            ("object_id", ">i8"),
            ("right_ascension", ">f8"),
            ("declination", ">f8"),
            ("tile_index", ">i8"),
            ("has_z_spec_good", "?"),
            ("z_spec_median_good", ">f4"),
            ("z_spec_sigma_good", ">f4"),
            ("id_2dFGRS", "S10"),
            ("pdf", ">f4", (4,)),
        ],
    )
    rows["object_id"] = -555684967664168129 + np.arange(n)
    rows["right_ascension"] = np.linspace(55.5, 55.6, n)
    rows["declination"] = np.linspace(-66.5, -66.4, n)
    rows["tile_index"] = 102006993
    rows["has_z_spec_good"] = [True, False] * (n // 2)
    rows["z_spec_median_good"] = 1.1
    path = os.path.join(directory, "euclid.fits")
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU(rows, name="GALAXIES")]).writeto(path)
    return path


class TestInspectAndSuggest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_ned_layout(self):
        table = find_table(inspect_columns(_ned_fits(self.dir)), None)
        self.assertEqual(table.hdu, 1)
        self.assertEqual(table.nrows, 6)
        self.assertEqual(table.column("ZFLAG").kind, gc.STR)
        self.assertEqual(table.column("ID_UNIQUE_CLUSTER").kind, gc.INT)
        self.assertEqual(
            suggest_mapping(table),
            {
                "RA": "RA",
                "DEC": "DEC",
                "SPEC_Z": "Z",
                "SPEC_Z_ERR": "ZUNC",
                "SPEC_Z_QUALITY": "ZFLAG",
                "CLUSTER_ID": "ID_UNIQUE_CLUSTER",
            },
        )
        self.assertIsNone(suggest_select_column(table))

    def test_euclid_layout(self):
        table = find_table(inspect_columns(_euclid_fits(self.dir)), None)
        self.assertEqual((table.hdu, table.name), (1, "GALAXIES"))
        self.assertEqual(table.column("has_z_spec_good").kind, gc.BOOL)
        self.assertEqual(table.column("pdf").kind, gc.ARRAY)
        self.assertEqual(
            suggest_mapping(table),
            {
                "RA": "right_ascension",
                "DEC": "declination",
                "OBJECT_ID": "object_id",
                "TILE_ID": "tile_index",
                "SPEC_Z": "z_spec_median_good",
                "SPEC_Z_ERR": "z_spec_sigma_good",
            },
        )
        self.assertEqual(suggest_select_column(table), "has_z_spec_good")
        self.assertNotIn("pdf", gc.compatible_columns(table, "SPEC_Z"))

    def test_other_formats(self):
        df = pd.DataFrame(
            {"ra": [10.0, 10.1], "dec": [-5.0, -5.1], "zspec": [0.3, 0.4], "name": ["a", "b"]}
        )
        csv = os.path.join(self.dir, "c.csv")
        df.to_csv(csv, index=False)
        parquet = os.path.join(self.dir, "c.parquet")
        df.to_parquet(parquet)
        ecsv = os.path.join(self.dir, "c.ecsv")
        Table.from_pandas(df).write(ecsv)
        expected = {"RA": "ra", "DEC": "dec", "SOURCE_ID": "name", "SPEC_Z": "zspec"}
        for path in (csv, parquet, ecsv):
            with self.subTest(path=path):
                table = find_table(inspect_columns(path), None)
                self.assertIsNone(table.hdu)
                self.assertEqual(suggest_mapping(table), expected)
                spec = CatalogSpec("x", path, expected)
                self.assertTrue(validate_mapping(spec).ok)
                cat = GalaxyCatalog(spec, cache_dir=os.path.join(self.dir, "cache"))
                self.assertTrue(cat.load(), cat.status)
                self.assertEqual(list(cat.df["SOURCE_ID"]), ["a", "b"])

    def test_direct_fits_read_matches_astropy(self):
        cols = [
            # uint64 stored the FITS way: signed values plus TZERO = 2**63 (set below)
            fits.Column(
                "u64",
                "K",
                array=(
                    np.array([1, 2**63 + 5, 2**64 - 1], dtype=np.uint64) ^ np.uint64(2**63)
                ).view(np.int64),
            ),
            fits.Column("s", "6A", array=np.array(["ab", "cdef", ""])),
            fits.Column("flag", "L", array=np.array([True, False, True])),
            fits.Column("scaled", "I", array=np.array([0, 3, -2], dtype=np.int16)),
            fits.Column("f", "E", array=np.array([1.5, np.nan, -2.0], dtype=np.float32)),
        ]
        path = os.path.join(self.dir, "types.fits")
        hdu = fits.BinTableHDU.from_columns(cols)
        hdu.header["TZERO1"] = 2**63
        hdu.header["TSCAL4"], hdu.header["TZERO4"] = 0.5, 10.0  # stored ints -> 10.0, 11.5, 9.0
        hdu.writeto(path)
        names = [c.name for c in cols]
        direct = gc._read_fits_rows(path, 1, names, None)
        self.assertIsNotNone(direct)
        with fits.open(path) as hdul:
            ref = hdul[1].data
            for name in names:
                with self.subTest(column=name):
                    np.testing.assert_array_equal(direct[name].to_numpy(), np.asarray(ref[name]))
        self.assertEqual(direct["u64"].dtype, np.uint64)
        self.assertEqual(len(gc._read_fits_rows(path, 1, ["f"], 2)), 2)

        gz = os.path.join(self.dir, "types.fits.gz")
        fits.BinTableHDU.from_columns(cols).writeto(gz)
        self.assertIsNone(gc._read_fits_rows(gz, 1, names, None))
        self.assertEqual(list(gc.read_columns(gz, ["s"])["s"]), ["ab", "cdef", ""])

    def test_bad_files(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            inspect_columns(os.path.join(self.dir, "missing.fits"))
        txt = os.path.join(self.dir, "x.txt")
        open(txt, "w").close()
        with self.assertRaisesRegex(ValueError, "unsupported"):
            inspect_columns(txt)


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ned = _ned_fits(self.tmp.name)
        self.euclid = _euclid_fits(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _errors(self, spec):
        return " | ".join(validate_mapping(spec).errors)

    def test_good_mapping(self):
        result = validate_mapping(CatalogSpec("NED", self.ned, {"RA": "RA", "DEC": "DEC"}))
        self.assertTrue(result.ok, result.errors)
        self.assertIn("6 rows", result.info[0])

    def test_errors(self):
        self.assertIn("required", self._errors(CatalogSpec("NED", self.ned, {"RA": "RA"})))
        self.assertIn(
            "expected", self._errors(CatalogSpec("NED", self.ned, {"RA": "ZFLAG", "DEC": "DEC"}))
        )
        self.assertIn(
            "no column", self._errors(CatalogSpec("NED", self.ned, {"RA": "nope", "DEC": "DEC"}))
        )
        self.assertIn(
            "same column", self._errors(CatalogSpec("NED", self.ned, {"RA": "RA", "DEC": "RA"}))
        )
        self.assertIn("name", self._errors(CatalogSpec(" ", self.ned, {"RA": "RA", "DEC": "DEC"})))
        base = {"RA": "right_ascension", "DEC": "declination"}
        self.assertIn(
            "expected bool",
            self._errors(CatalogSpec("E", self.euclid, base, select_column="object_id")),
        )
        self.assertIn(
            "arrays", self._errors(CatalogSpec("E", self.euclid, base, hover_columns=["pdf"]))
        )
        # Dec column used as RA: negative values
        self.assertIn(
            "RA: values", self._errors(CatalogSpec("NED", self.ned, {"RA": "DEC", "DEC": "RA"}))
        )
        df = pd.DataFrame({"ra": [10.0, 11.0], "dec": [95.0, 0.0]})
        path = os.path.join(self.tmp.name, "d.csv")
        df.to_csv(path, index=False)
        self.assertIn(
            "Dec: values", self._errors(CatalogSpec("D", path, {"RA": "ra", "DEC": "dec"}))
        )

    def test_ra_in_hours_warns(self):
        df = pd.DataFrame({"ra": np.linspace(1, 3, 20), "dec": np.zeros(20)})
        path = os.path.join(self.tmp.name, "h.csv")
        df.to_csv(path, index=False)
        result = validate_mapping(CatalogSpec("H", path, {"RA": "ra", "DEC": "dec"}))
        self.assertTrue(result.ok)
        self.assertIn("hours", result.warnings[0])


class TestGalaxyCatalog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.tmp.name, "cache")
        self.euclid = _euclid_fits(self.tmp.name)
        self.spec = CatalogSpec(
            "Euclid",
            self.euclid,
            {
                "RA": "right_ascension",
                "DEC": "declination",
                "OBJECT_ID": "object_id",
                "SPEC_Z": "z_spec_median_good",
            },
            hdu=1,
            select_column="has_z_spec_good",
            hover_columns=["id_2dFGRS"],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_standardizes_and_selects(self):
        cat = GalaxyCatalog(self.spec, cache_dir=self.cache)
        self.assertTrue(cat.load(), cat.status)
        self.assertEqual(list(cat.df.columns), ["RA", "DEC", "OBJECT_ID", "SPEC_Z", "id_2dFGRS"])
        self.assertEqual(len(cat.df), 4)
        self.assertEqual(cat.n_total, 8)
        self.assertEqual(cat.status, "4 galaxies of 8 (where has_z_spec_good)")
        self.assertEqual(cat.df["OBJECT_ID"].dtype, np.int64)
        self.assertEqual(int(cat.df["OBJECT_ID"].iloc[1]), -555684967664168129 + 2)
        self.assertEqual(cat.capabilities(), {"display", "match_position", "match_id", "specz"})
        self.assertEqual(len(cat.in_box(55.5, 55.55, -67, -66)), 2)
        self.assertEqual(len(cat.index.query_radius(55.5, -66.5, 0.001)), 1)

    def test_reads_only_mapped_columns_then_uses_cache(self):
        read = gc.read_columns
        with mock.patch.object(gc, "read_columns", side_effect=read) as spy:
            self.assertTrue(GalaxyCatalog(self.spec, cache_dir=self.cache).load())
        self.assertEqual(
            spy.call_args.args[1],
            [
                "right_ascension",
                "declination",
                "object_id",
                "z_spec_median_good",
                "has_z_spec_good",
                "id_2dFGRS",
            ],
        )
        with mock.patch.object(
            gc, "read_columns", side_effect=AssertionError("file read despite cache")
        ):
            cached = GalaxyCatalog(self.spec, cache_dir=self.cache)
            self.assertTrue(cached.load(), cached.status)
        self.assertEqual(cached.status, "4 galaxies of 8 (where has_z_spec_good)")
        self.assertEqual(len(cached.df), 4)

    def test_hover_columns(self):
        path = _ned_fits(self.tmp.name)
        spec = CatalogSpec("NED", path, {"RA": "RA", "DEC": "DEC"}, hover_columns=["ZREF", "R_MPC"])
        cat = GalaxyCatalog(spec, cache_dir=self.cache)
        self.assertTrue(cat.load(), cat.status)
        self.assertEqual(list(cat.df.columns), ["RA", "DEC", "ZREF", "R_MPC"])
        self.assertEqual(GalaxyCatalog.hover_name("SPEC_Z"), "SPEC_Z (column)")

    def test_cluster_ids_and_missing_file(self):
        path = _ned_fits(self.tmp.name)
        cat = GalaxyCatalog(
            CatalogSpec("NED", path, {"RA": "RA", "DEC": "DEC", "CLUSTER_ID": "ID_UNIQUE_CLUSTER"}),
            cache_dir=self.cache,
        )
        self.assertEqual(sorted(cat.cluster_ids().tolist()), [5, 259, 338])
        self.assertEqual(cat.status, "6 galaxies, 3 clusters")
        gone = GalaxyCatalog(
            CatalogSpec("X", os.path.join(self.tmp.name, "gone.fits"), {"RA": "a", "DEC": "b"})
        )
        self.assertFalse(gone.is_available())
        self.assertIn("not found", gone.status)
        self.assertEqual(len(gone.cluster_ids()), 0)


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "cfg", "catalogs.json")
        self.ned = _ned_fits(self.tmp.name)
        self.cache = os.path.join(self.tmp.name, "cache")

    def tearDown(self):
        self.tmp.cleanup()

    def _spec(self, name="NED spec-z"):
        return CatalogSpec(
            name, self.ned, {"RA": "RA", "DEC": "DEC", "CLUSTER_ID": "ID_UNIQUE_CLUSTER"}
        )

    def test_add_update_remove_persist(self):
        reg = CatalogRegistry(self.path, cache_dir=self.cache)
        cid = reg.add(self._spec())
        self.assertEqual(cid, "ned_spec_z")
        self.assertEqual(reg.add(self._spec("NED spec z!")), "ned_spec_z_2")
        with self.assertRaisesRegex(ValueError, "already exists"):
            reg.add(self._spec("ned SPEC-Z"))

        other = CatalogRegistry(self.path, cache_dir=self.cache)
        self.assertEqual([s.id for s in other.list()], ["ned_spec_z", "ned_spec_z_2"])
        self.assertEqual(other.get(cid).columns["CLUSTER_ID"], "ID_UNIQUE_CLUSTER")
        self.assertEqual(
            [s.id for s in other.with_capability("cluster_filter")], ["ned_spec_z", "ned_spec_z_2"]
        )

        spec = self._spec()
        spec.color = "#00aa00"
        reg.update(cid, spec)
        reg.remove("ned_spec_z_2")
        self.assertEqual(CatalogRegistry(self.path).get(cid).color, "#00aa00")
        self.assertEqual(len(CatalogRegistry(self.path).list()), 1)

    def test_other_process_changes_are_seen(self):
        ui = CatalogRegistry(self.path, cache_dir=self.cache)
        worker = CatalogRegistry(self.path, cache_dir=self.cache)
        self.assertEqual(worker.list(), [])
        cid = ui.add(self._spec())
        cat = worker.catalog(cid)
        self.assertIsNotNone(cat)
        self.assertIs(worker.catalog(cid), cat)  # same object while the spec is unchanged
        spec = self._spec()
        spec.color = "#123456"
        ui.update(cid, spec)
        os.utime(self.path, ns=(1, 1))  # same-tick writes: force an mtime the worker has not seen
        self.assertIsNot(worker.catalog(cid), cat)
        self.assertEqual(worker.catalog(cid).spec.color, "#123456")

    def test_import_legacy_once(self):
        reg = CatalogRegistry(self.path, cache_dir=self.cache)
        self.assertIsNone(reg.import_legacy(None))
        cid = reg.import_legacy(self.ned)
        self.assertEqual(cid, "ned_spec_z")
        self.assertEqual(reg.get(cid).columns["CLUSTER_ID"], "ID_UNIQUE_CLUSTER")
        self.assertEqual(reg.get(cid).columns["SPEC_Z"], "Z")
        self.assertIsNone(reg.import_legacy(self.ned))
        self.assertIsNone(reg.import_legacy(os.path.join(self.tmp.name, "missing.fits")))
        self.assertEqual(len(reg.list()), 1)


if __name__ == "__main__":
    unittest.main()
