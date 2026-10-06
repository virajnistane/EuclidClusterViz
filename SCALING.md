# Scaling ClusterViz with growing catalogs

Future work to keep the app responsive as cluster, CATRED and tile data grow.
Items are ordered by expected payoff. Check them off as they land.

Already in place: incremental "Apply filters" and same-algorithm Re-render
(only cluster traces rebuilt and patched with `dash.Patch`), per-catalog cache
of tile colours, opt-in figure-size logging (`CLUSTERVIZ_LOG_FIGURE_SIZE=1`),
CATRED viewport clipping and spatial index. Plotly 6.3 / Dash 2.18: numpy
arrays travel to the browser as typed binary, not JSON lists.

Tuning: `config.ini` `[view]` section: `cull_min_clusters` (default 5000; smaller
catalogs are sent whole), `max_points_sent` (default 50000; most clusters per
request, the margin around the view shrinks to fit) and `density_threshold`
(default 50000; above this many clusters in the visible area, a density grid
replaces markers).

**Suggested order:** 1 → 3 → 4 → 6 for the biggest gains as data grows; 9 → 10
once loading rather than drawing becomes the bottleneck; 13 before the app is
shared more widely.

## Biggest wins: send less to the browser

- [x] **1. Viewport culling.** Send only the cluster points inside the zoom
  window plus a margin, and patch them on zoom/pan (debounced). The payload then
  scales with what is on screen, not with catalog size.
  *Done:* `TraceCreator._cull_to_view` (100% margin each side, RA wrap-safe).
  The browser re-culls only when the view leaves the sent area; zoom-in never
  does. One request is in flight at a time, and moves made meanwhile are served
  when the patch lands. A thin `viewport-busy` bar shows while a request is
  pending. Simulated over 300 mixed gestures: 80 requests with the old 25%
  margin, 23 now.
- [x] **2. Level of detail when zoomed out.** Above a point-count threshold, show
  a binned density view (`go.Histogram2d`, or a datashader image) instead of
  individual markers; switch back to markers once zoomed in.
  *Done (2-D map):* `TraceCreator._density_trace`, a 120×120 heatmap. HEALPix
  density for the globe overview is planned next.
- [x] **3. Lighter per-point data.** Merged-cluster traces carry 9 customdata
  fields per point as Python lists, including pre-formatted strings
  (`TraceCreator._richness_arrays`). Send numeric arrays (or only the cluster ID)
  and fetch details on click. Upgrading to Plotly 6.x also sends arrays as typed
  binary instead of JSON lists.
  *Done:* customdata is a float array `[snr, z, det_code, id, tile_id]`; richness
  and flags moved to the Cluster data card. Plotly 6.3 + Dash 2.18; the Apply
  patch goes through `Figure.to_dict()` so it is binary too. Remaining weight:
  per-point tile colour strings (`marker.line.color`).
- [x] **4. Matched-pair ovals as one trace.** Up to 2,000 separate `go.Scatter`
  traces today, with pairs found by an O(N·M) Python loop
  (`TraceCreator._add_merged_cluster_trace`). Use a single trace with `None`
  separators and an ID-based lookup.
  *Done:* `TraceCreator._matched_pair_trace`; cap raised to 20,000 pairs.
- [x] **5. Unmerged clusters via KD-tree.** `_find_unmerged_mask` builds a dense
  N×M distance array; use `scipy.spatial.cKDTree` as tile colouring already does.
  *Done:* sparse pair search; the dense version remains as a fallback without scipy.

## Render pipeline

- [ ] **6. Stop uploading the whole figure.** Many callbacks take
  `State("cluster-plot", "figure")`, so the browser posts the full figure on each
  interaction. Keep overlay metadata in small stores or a per-session
  server-side figure cache. Also remove the `_originalData` copies the CATRED
  threshold clientside callback stores inside the figure.
- [x] **7. Merge polygon traces.** CL-tile LEV1/CORE outlines are two traces per
  tile, plus one per MER tile. Merge each type into one trace with `None`
  separators, and precompute the MER polygon lookup instead of a pandas `.loc`
  per tile.
  *Done:* outlines merged per type and style (`_merge_polygon_traces`, so tile
  colours are kept); MER polygons looked up from a per-catalog dict.
- [ ] **8. Cheaper background renders.** Each full render forks a process,
  pickles the figure into diskcache and is polled about once a second. Lower the
  polling interval, or move to a persistent worker pool (e.g. Celery + Redis).

## Data loading and memory

- [x] **9. Columnar storage.** Store catalogs as Parquet/Arrow (memory-mapped)
  instead of FITS plus pickle, and load only the columns the app uses.
  *Done:* the disk cache stores the merged catalog, tile rows (one file per
  column layout plus a small index) and members as zstd Parquet
  (`utils/columnar.py`, `DiskCache.get_table/set_table`), read with
  `memory_map=True` and optional column selection. The exact numpy dtype is
  kept in the schema metadata. Old pickle entries are rewritten as Parquet on
  first hit. Without pyarrow, or for object/variable-length columns, the old
  pickle path is used. The merged catalog keeps all columns (the Cluster data
  card shows them).
- [ ] **10. One catalog in memory.** PZWAV, AMICO and BOTH are loaded and cached
  separately although BOTH contains the other two. Load BOTH once and derive the
  per-algorithm views with masks.
- [x] **11. Cache the members catalog.** It is re-read from FITS in full on every
  load (`DataLoader`).
  *Done:* loaded on first use with only `MEMBER_COLUMNS` (ID_UNIQUE_CLUSTER,
  OBJECT_ID, PMEM_ZP, PMEM_RS), sorted by cluster ID, Parquet-cached, and shared
  by PZWAV/AMICO/BOTH (one copy per loader). Per-cluster lookup is a binary
  search (`DataLoader.members_for_cluster`) instead of a full scan.
- [ ] **12. Cache PHZ "Cluster data" results.** Filtered arrays are recomputed on
  every refresh; key a cache by filters and viewport.

## Multi-user and robustness

- [ ] **13. Per-session state.** Some state is shared across browser sessions:
  `ClusterModalCallbacks.selected_cluster`, `TraceCreator.current_catred_data`
  and the global `~/.cache/clusterviz_state` diskcache. Key it per session before
  more users or larger sessions.
- [ ] **14. Production server.** Run under gunicorn with several workers instead
  of the Dash development server; budget memory per worker, since each holds its
  own catalog caches.

## Measuring

- [ ] **15. Scale benchmarks.** Generate synthetic catalogs at 10× and 100×
  (`make_data()` in `cluster_visualization/tests/test_incremental_render.py`) and
  time Render, Apply filters and Re-render plus memory under `CLUSTERVIZ_PROFILE`.
  Fail CI on regressions.
- [ ] **16. Browser-side numbers.** Record payload size
  (`CLUSTERVIZ_LOG_FIGURE_SIZE=1`) and redraw time per zoom level, so items 1–3
  can be judged with data.
