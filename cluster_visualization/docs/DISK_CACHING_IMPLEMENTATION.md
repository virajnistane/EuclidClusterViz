# Disk Caching Guide

## Summary

Catalogs read from FITS are cached on disk so later server starts skip the FITS
reads. The large catalogs are stored as **Parquet** (columnar, zstd-compressed,
memory-mapped on read); small Python objects are stored as **pickle**.

- Module: `cluster_visualization/utils/disk_cache.py` (`DiskCache`)
- Parquet conversion: `cluster_visualization/utils/columnar.py`
- Users: `cluster_visualization/src/data/loader.py` (`DataLoader`)
- Location: `~/.cache/clusterviz/` (override with `CLUSTERVIZ_CACHE_DIR`)

## What Is Cached

| Cache key | Contents | Format |
|-----------|----------|--------|
| `merged_catalog_<ALG>` | Merged cluster catalog (all columns) plus the SNR min/max per algorithm in the file metadata | Parquet |
| `tile_rows_<ALG>_<n>` | Per-tile detection rows, one file per column layout (PZWAV and AMICO tiles differ) | Parquet |
| `tile_index_<ALG>` | Tile dictionary without the rows, plus each tile's row slice in `tile_rows_*` | pickle |
| `members` | Members catalog, pruned to `MEMBER_COLUMNS` and sorted by `ID_UNIQUE_CLUSTER` | Parquet |
| `catred_fileinfo` | CATRED file index (DataFrame) | pickle |

`<ALG>` is `PZWAV`, `AMICO` or `BOTH`.

### Parquet details

- `columnar.write_structured` writes each column in native byte order; vector
  columns become fixed-size lists. The exact numpy dtype (field order, string
  widths, vector shapes) and a small JSON `meta` dict travel in the schema
  metadata.
- `columnar.read_structured` reads with `memory_map=True` and can load only some
  columns; it returns a structured array whose rows allow attribute access, as
  `np.array(FITS_rec)` did.
- Tile rows are stored concatenated; on load each tile's `detfits_data` is a
  slice (a view, no copy) of its group array.

### Members catalog

The members FITS file is about 1 GB. It is not read at startup:

- It loads on the first **Members** click, with only `MEMBER_COLUMNS`
  (`ID_UNIQUE_CLUSTER`, `OBJECT_ID`, `PMEM_ZP`, `PMEM_RS`), sorted by cluster ID.
- One copy is shared by PZWAV, AMICO and BOTH.
- `DataLoader.members_for_cluster` finds a cluster's members with a binary
  search instead of scanning the whole table.
- After the first load it is answered from the `members` Parquet entry, also
  after a restart.

## Keys, Names and Invalidation

- An entry's key is its name plus an md5 of the source files' modification
  times, so editing or replacing a source FITS/XML file invalidates it.
- Files are named `{key}_{digest}.parquet` or `{key}_{digest}.pkl`.
- Entries older than 30 days are removed on access.
- Corrupt entries are deleted and rebuilt.

## Fallbacks

- **No pyarrow**: everything is cached as pickle, as before. pyarrow is listed
  in `requirements.txt` / `pyproject.toml` (`pyarrow>=17`).
- **Columns Parquet cannot hold** (object or variable-length): that entry falls
  back to pickle.
- **Old pickle entries** (`merged_catalog_*`, `tile_data_*`, `members_pruned`)
  are still read; on first hit they are rewritten as Parquet.

## Log Lines

```
✓ Loaded from cache: merged_catalog_PZWAV [parquet, 112 cols] (48.20 MB, 0.21 s, age: 2.0 hours)
✓ Saved to cache: members [parquet] (310.50 MB, 4.80 s)
```

## Cache Management

### Clear everything

```bash
./launch.sh --clear-cache   # removes ~/.cache/clusterviz, clusterviz_bg and clusterviz_state, then exits
```

### Inspect

```bash
ls -la ~/.cache/clusterviz/*.parquet ~/.cache/clusterviz/*.pkl
du -sh ~/.cache/clusterviz/
```

```python
from cluster_visualization.utils.disk_cache import get_default_cache

cache = get_default_cache()
info = cache.get_cache_info()
print(info["num_entries"], f"{info['total_size_mb']:.1f} MB")

cache.clear("merged_catalog_PZWAV")   # one entry (both .parquet and .pkl)
cache.clear()                         # everything
cache.cleanup_old_entries(max_age_days=7)
```

### Custom location

```bash
export CLUSTERVIZ_CACHE_DIR=/scratch/$USER/clusterviz_cache
```

## Troubleshooting

- **No `.parquet` files appear**: pyarrow is not installed in the app's
  environment (`python -c "import pyarrow"`). The app still works with pickle.
- **Data changed but the app shows old values**: the source file's mtime did
  not change (e.g. copied with preserved timestamps). Clear the entry or run
  `./launch.sh --clear-cache`.
- **Disk usage**: the members entry is the largest (a few hundred MB for the
  pruned columns). Old `.pkl` entries left from before the Parquet switch can
  be deleted by hand.

## Tests

`cluster_visualization/tests/test_columnar_cache.py` covers the Parquet round
trip, column selection, pickle fallback, tile tables and the members cache.
