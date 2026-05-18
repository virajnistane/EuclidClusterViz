# Plan: "Show CL-tile information" toggle

## TL;DR
Add `cltile-info-switch` (ON by default = current behavior). When OFF: skip all 9 `_compute_merged_tile_colors` calls → flat per-algorithm colors, simplified hover → enables A/B comparison to isolate whether UI lag comes from tile-color computation vs connection.

## Steps

### Phase 1 — UI
1. `sidebar_sections.py` `create_merged_clusters_section()` (~line 57): add `dbc.Switch(id="cltile-info-switch", label="Show CL-tile information", value=True)` below existing `unmerged-clusters-switch` card.

### Phase 2 — traces.py core logic
2. `create_traces()` signature (~line 56): add `show_cltile_info: bool = True` param; pass to `_add_merged_cluster_trace(...)` call (~line 164).
3. `_add_merged_cluster_trace()` signature (~line 722): add `show_cltile_info: bool = True` param.
4. All 9 `_compute_merged_tile_colors` call sites (~lines 853, 893, 954, 1019, 1061, 1124, 1181, 1237, 1307): change condition `if data_detcluster_by_cltile` → `if show_cltile_info and data_detcluster_by_cltile`; change fallback color from `"gray"` to flat per-algorithm: PZWAV→"royalblue", AMICO→"tomato".
5. All 9 hovertemplate title strings: make tile suffix conditional — True → `"<b>Cluster (PZWAV - Tile %{customdata[4]})</b><br>"`, False → `"<b>Cluster (PZWAV)</b><br>"`.

### Phase 3 — main_plot.py
6. `_setup_main_render_callback` State list: add `State("cltile-info-switch", "value")`; add `show_cltile_info` param to `update_plot()`; pass to `create_traces(...)`.
7. `_setup_options_update_callback` Input list: add `Input("cltile-info-switch", "value")`; add param; pass to `create_traces(...)`. *Parallel with step 6.*

### Phase 4 — cluster_modal_callbacks.py
8. `handle_tab_actions` State list (~line 620): add `State("cltile-info-switch", "value")`; add param; pass to `create_traces(...)` (~line 938).

### Phase 5 — catred_callbacks.py
9. `_setup_manual_catred_render_callback` State list + body (~line 154/258): add State, param, pass.
10. Second catred callback (~line 369/460): same pattern.
11. `CatredCallbacks.create_traces()` wrapper (~line 556): add `show_cltile_info: bool = True` param; pass through to both `trace_creator.create_traces(...)` and `_create_traces_fallback(...)`.

### Phase 6 — Verify
12. `get_errors` on all 5 modified files.

## Key implementation detail (9 call sites)
```python
(colors, tile_ids) = (
    self._compute_merged_tile_colors(X, data_detcluster_by_cltile)
    if (show_cltile_info and data_detcluster_by_cltile)
    else ([FLAT_COLOR] * len(X), ["?"] * len(X))
)
```
Flat colors: PZWAV → "royalblue", AMICO → "tomato".

## Decisions
- Default `value=True`: current behavior unchanged; user opts out for perf testing
- `cltile-info-switch` as **Input** to `_setup_options_update_callback` (instant re-render), **State** everywhere else (matches pattern of `unmerged-clusters-switch`)
- Scope: mergedcat traces only; unmerged traces have no tile coloring already
