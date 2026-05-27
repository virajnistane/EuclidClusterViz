# Viewport Optimization and CATRED Clipping Guide

## Overview

The MER (Multi-Epoch Reconstruction) CATRED (Reduced Catalog) data product covers large sky regions and can contain millions of photometric sources per tile. Rendering the full catalog in a Plotly figure causes severe browser slowdowns: large JSON payloads, long serialization times, and sluggish pan/zoom interactions.

To address this, ClusterViz clips CATRED source rendering to the **current map viewport** — only sources from tiles that intersect the visible RA/Dec window are loaded and sent to the browser. Combined with a diskcache layer for catalog metadata, subsequent re-renders after the initial load are substantially faster.

---

## CATRED Trace Clipping

### Zoom gate

The render button (`catred-render-button`) is enabled only when the viewport spans less than 2 degrees in both RA and Dec. This gate is enforced in two places:

- `CATREDCallbacks._setup_catred_button_state_callback` — disables the button whenever `ra_range >= 2.0` or `dec_range >= 2.0`.
- `TraceCreator._check_zoom_threshold` — returns `False` when the same condition is not met, preventing `_add_manual_catred_traces` from adding any trace even if data was somehow supplied.

When the MER switch (`mer-switch`) is off the button is always disabled regardless of zoom level.

### Viewport extraction

When the user clicks the CATRED render button, the callback reads the `relayoutData` from the Plotly figure. `CATREDHandler._extract_zoom_data_from_relayout` converts the Plotly axis keys into a plain dict:

```python
zoom_data = {
    "ra_min":  relayout_data["xaxis.range[0]"],
    "ra_max":  relayout_data["xaxis.range[1]"],
    "dec_min": relayout_data["yaxis.range[0]"],
    "dec_max": relayout_data["yaxis.range[1]"],
}
```

Both the flat `xaxis.range[0]` / `xaxis.range[1]` form and the list form `xaxis.range` are handled, because Plotly emits either depending on how the zoom was triggered.

### Tile intersection

`CATREDHandler._find_intersecting_tiles` builds a Shapely `box` from the four viewport bounds, then iterates over every row in `catred_info` whose `dataset_release` matches the configured `catred_dsr`, testing:

```python
if poly.intersects(zoom_box):
    mertiles_to_load.append(mertileid)
```

The `intersects` check is intentionally broad: it returns `True` if the tile polygon and the zoom box share any area, including the case where the zoom box is entirely inside a tile or the tile is entirely inside the zoom box. Only tiles that pass this test have their FITS data read from disk.

### Per-tile source loading

For each intersecting tile, one of three load paths is taken depending on the `catred_masked` parameter:

| Mode | Method | What is returned |
|------|--------|-----------------|
| Masked (`True`) | `get_radec_mertile_with_coverage` | Sources passing the effective-coverage threshold; full `EFFECTIVE_COVERAGE` column included for optional client-side re-filtering |
| Unmasked (`False`) | `get_radec_mertile` | All sources from the tile FITS file; magnitude filter still applied if `maglim < 99` |
| Cluster-box | `get_radec_mertile_masked` with `box=` | Masked sources additionally filtered to the RA/Dec/z box around a clicked cluster |

In the unmasked path (`get_radec_mertile`), if the FITS file is absent the handler falls back to `_get_polygon_fallback_data`, which populates the data dict with the tile polygon vertices and dummy photometric values so the figure is not empty. The masked and cluster-box paths (`get_radec_mertile_with_coverage`, `get_radec_mertile_masked`) do not have this fallback — they return `{}` on any error, which causes the tile to be silently skipped.

After loading, `_load_tile_data_with_coverage` (masked path) or `_load_tile_data_unmasked` (unmasked path) accumulates sources into a single `catred_scatter_data` dict with keys `ra`, `dec`, `phz_mode_1`, `phz_median`, `phz_70_int`, `phz_pdf`, `kron_radius`, `effective_coverage`. This flat dict is what `TraceCreator._add_manual_catred_traces` converts into a `go.Scattergl` trace.

### When clipping is bypassed

Clipping is skipped or inapplicable in these cases:

- The CATRED render button was never clicked — no CATRED traces exist yet and nothing is loaded.
- The viewport `relayout_data` is `None` or missing the `xaxis.range` keys (e.g. after initial page load before any pan/zoom). In this case `_extract_zoom_data_from_relayout` returns `{}` and the loading functions return empty structures immediately.
- Cluster-box mode (`update_catred_data_clusterbox`) uses the box around the clicked cluster rather than the plot viewport. The box is specified by `ra_min/ra_max/dec_min/dec_max/z_min/z_max` extracted from click data, and the same `_find_intersecting_tiles` geometry is used but with the cluster box instead of the viewport.

---

## Diskcache Optimization

### What is cached

`DataLoader` uses `cluster_visualization/utils/disk_cache.py` (`DiskCache` class) to persist three expensive operations to disk:

| Cache key | Content |
|-----------|---------|
| `merged_catalog_{algorithm}` | Processed merged cluster catalog array plus SNR min/max bounds (a 5-tuple) |
| `tile_data_{algorithm}` | Per-tile detection data dict keyed by tile ID |
| `catred_fileinfo` | CATRED file information DataFrame including polygon geometries |

A second, separate diskcache (`~/.cache/clusterviz_state`) stores `catred_click_data` — the most recently rendered CATRED scatter dict — so that the PHZ click callback (which runs in the main Dash process) can retrieve data written by the background CATRED render worker.

### Cache key structure

Each key is salted with the `mtime` of each source file:

```
{logical_key}_{md5("{logical_key}|{file1}:{mtime1}|{file2}:{mtime2}|...")}
```

This means the same logical key (`merged_catalog_PZWAV`) resolves to a different file on disk whenever any input FITS or XML file is modified, so stale data is never returned silently.

### Invalidation rules

A cache entry is considered invalid and is deleted when:

- Any source file listed during `DiskCache.set` has a newer `mtime` at read time (the key hash changes, the old file is not found).
- The cache file is older than `max_age_days` (default 30 days).

Manual invalidation is available via:

```python
loader.clear_disk_cache()                       # clear all entries
loader.clear_disk_cache("merged_catalog_PZWAV") # clear one entry
```

The `UICallbacks._setup_file_configuration_callback` clears the in-memory dict (`data_loader.data_cache`) whenever the user switches to a different GlueMatchCat XML file at runtime. It also attempts to clear `merged_catalog` keys from the diskcache, but the disk-cache invalidation code checks `self.data_loader.cached` which does not exist on `DataLoader` (the attribute is `disk_cache`), so disk cache entries for the previous file are not actually removed and will be evicted only by the normal mtime-based invalidation.

### Cache directory

Default path: `~/.cache/clusterviz/`

Override with the environment variable:

```bash
export CLUSTERVIZ_CACHE_DIR=/scratch/username/clusterviz_cache
```

---

## Serverside Mask Controls Toggle

### What moved serverside

The `_setup_mask_overlay_callback` in `MOSAICCallbacks` runs **serverside** (i.e. as a standard Dash Python callback rather than a `clientside_callback`). When the user clicks the "HEALPix Mask" button, the server:

1. Loads the current algorithm data via `data_loader.load_data(algorithm)`.
2. Calls `mosaic_handler.load_mask_overlay_traces_in_zoom(...)` to build HEALPix footprint traces for the current viewport.
3. Reconstructs the trace layer order — polygon traces → mosaic traces → mosaic cutout traces → mask overlay traces → CATRED traces → other traces → cluster traces — and returns the updated figure to the browser.

The delete callback (`_setup_mask_delete_callback`) is also serverside: it filters all traces whose `name` starts with `Mask overlay` or equals `Mask Colorbar` out of the figure dict and returns the trimmed figure.

### What stayed clientside

The **visibility toggle** (`_setup_mask_visibility_toggle_callback`) and the **button enable/disable state** callback (`_setup_mask_control_buttons_state_callback`) are both `app.clientside_callback` implementations. They inspect the figure JSON in the browser without a round-trip, which keeps show/hide interactions instant regardless of figure size.

### Why this split

Rendering a HEALPix mask requires loading FITS files and running healpy coordinate transforms — work that cannot be done in the browser. The delete operation also needs to mutate the figure dict reliably, and keeping it serverside avoids edge-case races with the Plotly figure store. The show/hide toggle only changes a `visible` property on already-loaded traces, so it runs entirely clientside for maximum responsiveness.

---

## Performance Impact

The user observes the following behaviour differences compared to a naive full-sky render:

- **Initial page load**: cluster catalog tiles load at normal speed; no CATRED data appears until the user zooms in and presses the render button.
- **CATRED render**: only sources from tiles intersecting the current 2° × 2° (or smaller) window are serialized and sent to the browser. For a typical zoom window this is tens of thousands of sources rather than tens of millions.
- **Pan/zoom after first render**: the figure re-renders with the existing CATRED trace in place (existing traces are extracted from the current figure and re-injected via `_extract_existing_catred_traces`). A new render button click is required only if the user wants sources from newly visible tiles.
- **Subsequent application launches**: `DataLoader` loads merged catalogs and tile metadata from the diskcache (`~/.cache/clusterviz/`) rather than re-reading FITS files, reducing startup time by 5–10×.
- **Mask overlay**: the HEALPix footprint is computed on the server for only the pixels that fall inside the current viewport (`_get_mask_footprint_in_viewport`), keeping the trace payload small even for high-resolution masks.

---

## Related Files

- `cluster_visualization/callbacks/catred_callbacks.py` — CATRED render/clear/visibility callbacks
- `cluster_visualization/src/data/catred_handler.py` — Tile intersection, FITS loading, masking logic
- `cluster_visualization/src/visualization/traces.py` — Zoom gate, trace assembly, diskcache state write
- `cluster_visualization/callbacks/ui_callbacks.py` — CATRED controls visibility (clientside)
- `cluster_visualization/callbacks/mosaic_callback.py` — Serverside mask overlay render and delete
- `cluster_visualization/utils/disk_cache.py` — `DiskCache` class
- `cluster_visualization/src/data/loader.py` — `DataLoader` with diskcache integration
