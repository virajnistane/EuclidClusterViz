"""
Galaxy catalog callbacks: the Galaxy catalogs section (list and Add/Edit dialog),
catalog markers on the plot, and CATRED sources near the shown catalogs.

Catalogs come from CatalogRegistry (per-user JSON). A catalog is loaded the first
time it is shown; catalogs too large to draw whole are drawn for the current view
and redrawn as the view moves (see catalog_traces.select_for_display).
"""

import os
import time

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, ctx, html
from dash.exceptions import PreventUpdate
from loguru import logger

from cluster_visualization.src.data.catalog_matcher import (
    file_stem,
    match_by_id,
    match_by_position,
    spec_z_values,
    write_matches,
)
from cluster_visualization.src.data.galaxy_catalog import (
    ARRAY,
    BOOL,
    ROLES,
    CatalogSpec,
    ColumnInfo,
    TableInfo,
    compatible_columns,
    inspect_columns,
    suggest_mapping,
    suggest_select_column,
    validate_mapping,
)
from cluster_visualization.src.visualization.catalog_traces import (
    KIND_CATALOG,
    MATCH_PREFIX,
    build_catalog_trace,
    build_match_trace,
    match_trace_name,
    select_for_display,
    trace_meta,
)
from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType
from cluster_visualization.ui.catalog_controls import CatalogControls

CATALOG_TYPES = {TraceType.GALAXY_CATALOG, TraceType.CATALOG_MATCH}
HIDDEN = {"display": "none"}
SHOWN = {"display": "block"}
# Colours offered to new catalogs, the first one no other catalog uses
PALETTE = ("#ff8800", "#d62728", "#2ca02c", "#9467bd", "#17becf", "#e377c2", "#8c564b", "#bcbd22")
ALL_SHOW = {"type": "catalog-show", "index": ALL}


def parse_axis_range(relayout_data, axis_prefix):
    """(min, max) of an axis from relayoutData, in either form Plotly emits
    ("xaxis.range[0]"/"[1]" after a box zoom, "xaxis.range": [a, b] otherwise)."""
    if not relayout_data:
        return None
    key0, key1, key_list = (
        f"{axis_prefix}.range[0]",
        f"{axis_prefix}.range[1]",
        f"{axis_prefix}.range",
    )
    if key0 in relayout_data and key1 in relayout_data:
        return relayout_data[key0], relayout_data[key1]
    if key_list in relayout_data and len(relayout_data[key_list]) == 2:
        return relayout_data[key_list][0], relayout_data[key_list][1]
    return None


def current_viewport(relayout_data, figure=None):
    """RA/Dec box on screen: relayoutData, else the figure's own axis ranges; None if unknown."""
    ra_range = parse_axis_range(relayout_data, "xaxis")
    dec_range = parse_axis_range(relayout_data, "yaxis")
    layout = (figure or {}).get("layout", {}) or {}
    if ra_range is None:
        xr = (layout.get("xaxis") or {}).get("range")
        ra_range = tuple(xr) if xr and len(xr) == 2 else None
    if dec_range is None:
        yr = (layout.get("yaxis") or {}).get("range")
        dec_range = tuple(yr) if yr and len(yr) == 2 else None
    if ra_range is None or dec_range is None:
        return None
    ra_min, ra_max = sorted(float(v) for v in ra_range)
    dec_min, dec_max = sorted(float(v) for v in dec_range)
    return {"ra_min": ra_min, "ra_max": ra_max, "dec_min": dec_min, "dec_max": dec_max}


def _tables_to_store(path, tables):
    return {
        "path": path,
        "tables": [
            {
                "hdu": t.hdu,
                "name": t.name,
                "nrows": t.nrows,
                "columns": [[c.name, c.kind, c.dtype, c.unit] for c in t.columns],
            }
            for t in tables
        ],
    }


def _table_from_store(store, index) -> TableInfo:
    t = store["tables"][index]
    return TableInfo(t["hdu"], t["name"], t["nrows"], tuple(ColumnInfo(*c) for c in t["columns"]))


def _table_label(table: TableInfo) -> str:
    rows = f"{table.nrows:,} rows" if table.nrows is not None else "rows unknown"
    where = f"HDU {table.hdu}, " if table.hdu is not None else ""
    return f"{table.name} ({where}{rows}, {len(table.columns)} columns)"


def _column_options(columns):
    return [
        {"label": f"{c.name}  ({c.kind}{', ' + c.unit if c.unit else ''})", "value": c.name}
        for c in columns
    ]


def _alert(text, color):
    return dbc.Alert(text, color=color, className="py-1 px-2 mb-1 small")


def _feedback(result):
    return (
        [_alert(e, "danger") for e in result.errors]
        + [_alert(w, "warning") for w in result.warnings]
        + [_alert(i, "secondary") for i in result.info]
    )


def _triggered_value():
    """Value of the input that fired; 0/None when a re-rendered pattern component fired it."""
    return ctx.triggered[0]["value"] if ctx.triggered else None


def format_catred_hover(catred_scatter, idx, title):
    """Hover text for matched CATRED sources (same fields as the CATRED trace)."""
    phz_median = catred_scatter.get("phz_median", [])
    phz_mode_1 = catred_scatter.get("phz_mode_1", [])
    phz_70_int = catred_scatter.get("phz_70_int", [])
    coverage = catred_scatter.get("effective_coverage", [])
    texts = []
    for i in idx:
        text = f"<b>{title}</b><br>RA: {catred_scatter['ra'][i]:.6f}<br>Dec: {catred_scatter['dec'][i]:.6f}"
        if i < len(phz_mode_1):
            text += f"<br>PHZ_MODE_1: {phz_mode_1[i]:.3f}"
        if i < len(phz_median):
            text += f"<br>PHZ_MEDIAN: {phz_median[i]:.3f}"
        if i < len(phz_70_int):
            p70 = phz_70_int[i]
            text += f"<br>PHZ_70_INT: {abs(float(p70[1]) - float(p70[0])):.3f}"
        if i < len(coverage):
            text += f"<br>Effective Coverage: {coverage[i]:.3f}"
        texts.append(text)
    return texts


class CatalogCallbacks:
    """Callbacks of the Galaxy catalogs section."""

    def __init__(self, app, registry, catred_handler=None, data_loader=None):
        """
        Args:
            app: Dash application instance
            registry: CatalogRegistry with the user's catalogs
            catred_handler: CATREDHandler, to load CATRED sources near catalog galaxies
                and to hold click data for the p(z) plot
            data_loader: DataLoader, for the tile data the CATRED handler needs
        """
        self.app = app
        self.registry = registry
        self.catred_handler = catred_handler
        self.data_loader = data_loader

        self._setup_list_callback()
        self._setup_dialog_callbacks()
        self._setup_remove_callback()
        self._setup_show_callback()
        self._setup_window_callbacks()
        self._setup_match_button_state_callback()
        self._setup_match_callback()

    # ------------------------------------------------------------------
    # Figure helpers
    # ------------------------------------------------------------------

    def _catalog_trace(self, catalog_id, viewport):
        """(trace or None, status text) for a catalog about to be shown."""
        catalog = self.registry.catalog(catalog_id)
        if catalog is None:
            return None, "no longer in the list"
        if not catalog.is_available():
            return None, f"⚠ {catalog.status}"
        df, total, windowed = select_for_display(catalog, viewport)
        status = catalog.status + ("; large, drawn for the current view" if windowed else "")
        return build_catalog_trace(catalog.spec, df, total, windowed), status

    @staticmethod
    def _catalog_ids(traces):
        return {trace_meta(t).get("catalog_id") for t in traces}

    def _forget_click_data(self, names=None):
        """Drop stored p(z) click data of catalog match traces (all, or ``names``)."""
        data = getattr(self.catred_handler, "current_catred_data", None)
        if not data:
            return
        for key in [k for k in data if isinstance(k, str) and k.startswith(MATCH_PREFIX)]:
            if names is None or key in names:
                del data[key]

    def _store_click_data(self, spec, result, galaxies):
        """Register matched CATRED rows under the match trace's name, in point order, so a
        click on one shows its p(z) (PHZCallbacks indexes this by the clicked pointNumber),
        with the spec-z of the catalog galaxy each source belongs to."""
        if self.catred_handler is None:
            return
        if self.catred_handler.current_catred_data is None:
            self.catred_handler.current_catred_data = {}
        scatter, idx = result.catred_scatter, result.display_matched_idx
        n = len(scatter["ra"])
        click = {
            key: [scatter[key][i] for i in idx]
            for key in ("ra", "dec", "phz_pdf", "phz_mode_1", "phz_median", "phz_70_int")
            if len(scatter.get(key, [])) == n
        }
        click.update(spec_z_values(galaxies, result.display_galaxy_idx, len(idx)))
        click["catalog"] = [spec.name] * len(idx)
        self.catred_handler.current_catred_data[match_trace_name(spec)] = click

    def _without_catalogs(self, figure, catalog_ids):
        """Figure without the traces of ``catalog_ids``; no_update if it has none."""
        if not figure or "data" not in figure:
            return dash.no_update
        data = [t for t in figure["data"] if trace_meta(t).get("catalog_id") not in catalog_ids]
        if len(data) == len(figure["data"]):
            return dash.no_update
        figure["data"] = data
        return figure

    # ------------------------------------------------------------------
    # List and dialog
    # ------------------------------------------------------------------

    def _setup_list_callback(self):
        @self.app.callback(
            Output("catalog-list", "children"),
            Input("catalog-registry-version", "data"),
            State(ALL_SHOW, "value"),
            State(ALL_SHOW, "id"),
        )
        def render_catalog_list(_version, values, ids):
            shown = {i["index"] for i, v in zip(ids, values) if v}
            return CatalogControls.catalog_rows(self.registry.list(), shown)

    def _setup_dialog_callbacks(self):
        @self.app.callback(
            Output("catalog-modal", "is_open"),
            Output("catalog-modal-state", "data"),
            Output("catalog-modal-title", "children"),
            Output("catalog-path-input", "value"),
            Output("catalog-path-feedback", "children"),
            Output("catalog-mapping-section", "style"),
            Output("catalog-check-feedback", "children"),
            Input("catalog-add-button", "n_clicks"),
            Input({"type": "catalog-edit", "index": ALL}, "n_clicks"),
            Input("catalog-cancel-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def open_catalog_dialog(_add, _edits, _cancel):
            if not _triggered_value():
                raise PreventUpdate
            trigger = ctx.triggered_id
            if trigger == "catalog-cancel-button":
                return (False,) + (dash.no_update,) * 6
            # "t" makes every opening a new value, so the read callback fires for a repeated Edit
            if trigger == "catalog-add-button":
                return (
                    True,
                    {"mode": "add", "t": time.time()},
                    "Add galaxy catalog",
                    "",
                    None,
                    HIDDEN,
                    None,
                )
            spec = self.registry.get(trigger["index"])
            if spec is None:
                raise PreventUpdate
            state = {"mode": "edit", "id": spec.id, "spec": spec.to_dict(), "t": time.time()}
            return True, state, f"Edit {spec.name}", spec.path, None, HIDDEN, None

        @self.app.callback(
            Output("catalog-table-store", "data"),
            Output("catalog-hdu-dropdown", "options"),
            Output("catalog-hdu-dropdown", "value"),
            Output("catalog-hdu-row", "style"),
            Output("catalog-path-feedback", "children", allow_duplicate=True),
            Output("catalog-mapping-section", "style", allow_duplicate=True),
            Input("catalog-read-button", "n_clicks"),
            Input("catalog-path-input", "n_submit"),
            Input("catalog-modal-state", "data"),
            State("catalog-path-input", "value"),
            prevent_initial_call=True,
        )
        def read_catalog_columns(_n, _submit, state, path):
            state = state or {}
            if ctx.triggered_id == "catalog-modal-state" and state.get("mode") != "edit":
                raise PreventUpdate
            path = os.path.expanduser((path or "").strip())
            if not path:
                return (
                    None,
                    [],
                    None,
                    HIDDEN,
                    _alert("Enter the path of a catalog file.", "warning"),
                    HIDDEN,
                )
            try:
                tables = inspect_columns(path)
            except ValueError as e:
                return None, [], None, HIDDEN, _alert(str(e), "danger"), HIDDEN
            index = 0
            spec = state.get("spec") if state.get("mode") == "edit" else None
            if spec and os.path.realpath(spec["path"]) == os.path.realpath(path):
                index = next((i for i, t in enumerate(tables) if t.hdu == spec.get("hdu")), 0)
            options = [{"label": _table_label(t), "value": i} for i, t in enumerate(tables)]
            feedback = html.Small(_table_label(tables[index]), className="control-help")
            hdu_style = SHOWN if len(tables) > 1 else HIDDEN
            return _tables_to_store(path, tables), options, index, hdu_style, feedback, SHOWN

        role_outputs = []
        for role in ROLES:
            role_outputs += [
                Output(f"catalog-role-{role.name}", "options"),
                Output(f"catalog-role-{role.name}", "value"),
            ]

        @self.app.callback(
            *role_outputs,
            Output("catalog-select-dropdown", "options"),
            Output("catalog-select-dropdown", "value"),
            Output("catalog-hover-dropdown", "options"),
            Output("catalog-hover-dropdown", "value"),
            Output("catalog-name-input", "value"),
            Output("catalog-color-input", "value"),
            Output("catalog-symbol-dropdown", "value"),
            Output("catalog-check-feedback", "children", allow_duplicate=True),
            Input("catalog-table-store", "data"),
            Input("catalog-hdu-dropdown", "value"),
            State("catalog-modal-state", "data"),
            prevent_initial_call=True,
        )
        def fill_catalog_mapping(store, index, state):
            if not store or index is None:
                raise PreventUpdate
            table = _table_from_store(store, index)
            state = state or {}
            spec = state.get("spec") if state.get("mode") == "edit" else None
            same_table = bool(
                spec
                and os.path.realpath(spec["path"]) == os.path.realpath(store["path"])
                and spec.get("hdu") == table.hdu
            )
            if same_table:
                mapping = spec.get("columns") or {}
                select = spec.get("select_column")
                hover = spec.get("hover_columns") or []
            else:
                mapping = suggest_mapping(table)
                select = suggest_select_column(table)
                hover = []

            out = []
            for role in ROLES:
                names = compatible_columns(table, role.name)
                columns = [c for c in table.columns if c.name in names]
                value = mapping.get(role.name)
                out += [_column_options(columns), value if value in names else None]
            bools = [c for c in table.columns if c.kind == BOOL]
            hoverable = [c for c in table.columns if c.kind != ARRAY]
            hover_names = {c.name for c in hoverable}

            # Name, colour and marker only when a file is (re)read, not when switching tables
            if ctx.triggered_id == "catalog-table-store":
                if spec:
                    name, color, symbol = spec["name"], spec.get("color"), spec.get("symbol")
                else:
                    used = {s.color.lower() for s in self.registry.list()}
                    name = file_stem(store["path"])
                    color = next((c for c in PALETTE if c not in used), PALETTE[0])
                    symbol = "diamond"
            else:
                name = color = symbol = dash.no_update
            return (
                *out,
                _column_options(bools),
                select if select in {c.name for c in bools} else None,
                _column_options(hoverable),
                [h for h in hover if h in hover_names],
                name,
                color,
                symbol,
                None,
            )

        @self.app.callback(
            Output("catalog-check-feedback", "children", allow_duplicate=True),
            Output("catalog-modal", "is_open", allow_duplicate=True),
            Output("catalog-registry-version", "data"),
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("catalog-check-button", "n_clicks"),
            Input("catalog-save-button", "n_clicks"),
            State("catalog-table-store", "data"),
            State("catalog-hdu-dropdown", "value"),
            *[State(f"catalog-role-{role.name}", "value") for role in ROLES],
            State("catalog-select-dropdown", "value"),
            State("catalog-hover-dropdown", "value"),
            State("catalog-name-input", "value"),
            State("catalog-color-input", "value"),
            State("catalog-symbol-dropdown", "value"),
            State("catalog-modal-state", "data"),
            State("catalog-registry-version", "data"),
            State("cluster-plot", "figure"),
            State("cluster-plot", "relayoutData"),
            prevent_initial_call=True,
        )
        def check_or_save_catalog(_check, _save, store, index, *values):
            if not _triggered_value():
                raise PreventUpdate
            no = dash.no_update
            role_values = values[: len(ROLES)]
            select, hover, name, color, symbol, state, version, figure, relayout = values[
                len(ROLES) :
            ]
            if not store or index is None:
                return _alert("Read the file's columns first.", "warning"), no, no, no
            table = _table_from_store(store, index)
            spec = CatalogSpec(
                name=(name or "").strip(),
                path=store["path"],
                columns={role.name: v for role, v in zip(ROLES, role_values) if v},
                hdu=table.hdu,
                select_column=select or None,
                hover_columns=list(hover or []),
                color=color or PALETTE[0],
                symbol=symbol or "diamond",
            )
            result = validate_mapping(spec, table)
            if ctx.triggered_id == "catalog-check-button" or not result.ok:
                return _feedback(result), no, no, no

            state = state or {}
            try:
                if state.get("mode") == "edit":
                    self.registry.update(state["id"], spec)
                else:
                    self.registry.add(spec)
            except ValueError as e:
                return [_alert(str(e), "danger")], no, no, no

            # An edited catalog that is on the plot is redrawn with its new mapping and style
            figure_out = no
            if state.get("mode") == "edit":
                self._forget_click_data({match_trace_name(CatalogSpec.from_dict(state["spec"]))})
                shown = figure and any(
                    trace_meta(t).get("catalog_id") == spec.id
                    and trace_meta(t).get("kind") == KIND_CATALOG
                    for t in figure.get("data", [])
                )
                if shown:
                    figure = self._without_catalogs(figure, {spec.id})
                    trace, _ = self._catalog_trace(spec.id, current_viewport(relayout, figure))
                    categorized = TraceRegistry.categorize_all(figure)
                    if trace is not None:
                        categorized[TraceType.GALAXY_CATALOG].append(trace)
                    figure["data"] = TraceRegistry.assemble_in_layer_order(categorized)
                    figure_out = figure
            return None, False, (version or 0) + 1, figure_out

    def _setup_remove_callback(self):
        @self.app.callback(
            Output("catalog-registry-version", "data", allow_duplicate=True),
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input({"type": "catalog-remove", "index": ALL}, "n_clicks"),
            State("catalog-registry-version", "data"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )
        def remove_catalog(_clicks, version, figure):
            if not _triggered_value():
                raise PreventUpdate
            catalog_id = ctx.triggered_id["index"]
            spec = self.registry.get(catalog_id)
            self.registry.remove(catalog_id)
            if spec is not None:
                self._forget_click_data({match_trace_name(spec)})
            return (version or 0) + 1, self._without_catalogs(figure, {catalog_id})

    # ------------------------------------------------------------------
    # Markers
    # ------------------------------------------------------------------

    def _setup_show_callback(self):
        @self.app.callback(
            Output("cluster-plot", "figure", allow_duplicate=True),
            Output({"type": "catalog-status", "index": ALL}, "children"),
            Input(ALL_SHOW, "value"),
            State(ALL_SHOW, "id"),
            State({"type": "catalog-status", "index": ALL}, "children"),
            State("cluster-plot", "figure"),
            State("cluster-plot", "relayoutData"),
            prevent_initial_call=True,
        )
        def show_catalogs(values, ids, statuses, figure, relayout):
            """Draw the catalogs switched on and remove the ones switched off.

            Reconciles switches with the figure rather than acting on the one switch
            that changed: the list is re-rendered after Add/Edit/Remove, which fires
            this for every switch at once.
            """
            if not figure or "data" not in figure:
                raise PreventUpdate
            order = [i["index"] for i in ids]
            wanted = [cid for cid, on in zip(order, values) if on]
            existing = TraceRegistry.extract_traces(figure, CATALOG_TYPES, reconstruct=False)
            present = self._catalog_ids(existing[TraceType.GALAXY_CATALOG])
            to_draw = [cid for cid in wanted if cid not in present]
            to_hide = present - set(wanted)
            if not to_draw and not to_hide:
                raise PreventUpdate

            categorized = TraceRegistry.extract_all_preserved(figure, exclude=CATALOG_TYPES)
            catalog_traces = [
                t
                for t in existing[TraceType.GALAXY_CATALOG]
                if trace_meta(t).get("catalog_id") not in to_hide
            ]
            # Hiding a catalog also removes its CATRED matches
            match_traces = []
            for t in existing[TraceType.CATALOG_MATCH]:
                if trace_meta(t).get("catalog_id") in to_hide:
                    self._forget_click_data({t.get("name")})
                else:
                    match_traces.append(t)

            status = dict(zip(order, statuses))
            viewport = current_viewport(relayout, figure)
            for cid in to_draw:
                trace, status[cid] = self._catalog_trace(cid, viewport)
                if trace is not None:
                    catalog_traces.append(trace)

            categorized[TraceType.GALAXY_CATALOG] = catalog_traces
            categorized[TraceType.CATALOG_MATCH] = match_traces
            figure["data"] = TraceRegistry.assemble_in_layer_order(categorized)
            return figure, [status[cid] for cid in order]

    def _setup_window_callbacks(self):
        """Redraw large catalogs for the new view after a zoom or pan.

        The server only computes the new traces (into catalog-window-store); the
        browser swaps them into its current figure by catalog id, so a render that
        finished meanwhile is not overwritten with an older figure.
        """

        @self.app.callback(
            Output("catalog-window-store", "data"),
            Input("cluster-plot", "relayoutData"),
            State(ALL_SHOW, "value"),
            State(ALL_SHOW, "id"),
            prevent_initial_call=True,
        )
        def window_catalogs(relayout, values, ids):
            if not relayout or not any(str(k).startswith(("xaxis", "yaxis")) for k in relayout):
                raise PreventUpdate
            viewport = current_viewport(relayout)  # None after a reset: the whole sky, thinned
            traces = []
            for i, on in zip(ids, values):
                catalog = self.registry.catalog(i["index"]) if on else None
                if catalog is None or catalog.df is None:
                    continue
                df, total, windowed = select_for_display(catalog, viewport)
                if windowed:
                    traces.append(
                        build_catalog_trace(catalog.spec, df, total, True).to_plotly_json()
                    )
            if not traces:
                raise PreventUpdate
            return {"traces": traces, "t": time.time()}

        self.app.clientside_callback(
            """
            function(payload, figure) {
                var NO = window.dash_clientside.no_update;
                if (!payload || !payload.traces || !figure || !figure.data) { return NO; }
                var byId = {};
                payload.traces.forEach(function(t) { if (t.meta) { byId[t.meta.catalog_id] = t; } });
                var changed = false;
                var data = figure.data.map(function(t) {
                    var m = t.meta || {};
                    if (m.kind === 'catalog' && byId[m.catalog_id]) { changed = true; return byId[m.catalog_id]; }
                    return t;
                });
                return changed ? Object.assign({}, figure, {data: data}) : NO;
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("catalog-window-store", "data"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

    # ------------------------------------------------------------------
    # CATRED near shown catalogs
    # ------------------------------------------------------------------

    def _setup_match_button_state_callback(self):
        """Enable the button only once data is rendered and the view is under 2° × 2°
        (the same gate as the CATRED render button), so CATRED is never loaded for a
        whole-survey view."""
        self.app.clientside_callback(
            """
            function(relayoutData, nClicks, figure) {
                if (!nClicks) return true;
                var raRange = null, decRange = null;
                if (relayoutData) {
                    if ('xaxis.range[0]' in relayoutData && 'xaxis.range[1]' in relayoutData) {
                        raRange = Math.abs(relayoutData['xaxis.range[1]'] - relayoutData['xaxis.range[0]']);
                    } else if (relayoutData['xaxis.range']) {
                        raRange = Math.abs(relayoutData['xaxis.range'][1] - relayoutData['xaxis.range'][0]);
                    }
                    if ('yaxis.range[0]' in relayoutData && 'yaxis.range[1]' in relayoutData) {
                        decRange = Math.abs(relayoutData['yaxis.range[1]'] - relayoutData['yaxis.range[0]']);
                    } else if (relayoutData['yaxis.range']) {
                        decRange = Math.abs(relayoutData['yaxis.range'][1] - relayoutData['yaxis.range'][0]);
                    }
                }
                if ((raRange === null || decRange === null) && figure && figure.layout) {
                    var layout = figure.layout;
                    if (layout.xaxis && layout.xaxis.range && layout.xaxis.range.length === 2) {
                        raRange = Math.abs(layout.xaxis.range[1] - layout.xaxis.range[0]);
                    }
                    if (layout.yaxis && layout.yaxis.range && layout.yaxis.range.length === 2) {
                        decRange = Math.abs(layout.yaxis.range[1] - layout.yaxis.range[0]);
                    }
                }
                return !(raRange !== null && decRange !== null && raRange < 2.0 && decRange < 2.0);
            }
            """,
            Output("catalog-match-button", "disabled"),
            Input("cluster-plot", "relayoutData"),
            [State("render-button", "n_clicks"), State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )

    def _setup_match_callback(self):
        @self.app.callback(
            Output("cluster-plot", "figure", allow_duplicate=True),
            Output("catalog-match-feedback", "children"),
            Input("catalog-match-button", "n_clicks"),
            State("catalog-match-radius-arcsec", "value"),
            State("algorithm-dropdown", "value"),
            State("catred-mode-switch", "value"),
            State("catred-threshold-slider", "value"),
            State("magnitude-limit-slider", "value"),
            State("cluster-plot", "relayoutData"),
            State("cluster-plot", "figure"),
            State(ALL_SHOW, "value"),
            State(ALL_SHOW, "id"),
            prevent_initial_call=True,
        )
        def load_catred_near_catalogs(
            n_clicks,
            radius_arcsec,
            algorithm,
            catred_masked,
            threshold,
            maglim,
            relayout,
            figure,
            values,
            ids,
        ):
            if not n_clicks or not figure or "data" not in figure:
                raise PreventUpdate
            shown = [i["index"] for i, on in zip(ids, values) if on]
            if not shown:
                return dash.no_update, "Show a catalog first."
            viewport = current_viewport(relayout, figure)
            if viewport is None:
                return dash.no_update, "Zoom in first."
            if self.catred_handler is None or self.data_loader is None:
                return dash.no_update, "CATRED is not available."

            data = self.data_loader.load_data(algorithm)
            self._forget_click_data()
            traces, notes = [], []
            for cid in shown:
                catalog = self.registry.catalog(cid)
                if catalog is None or not catalog.is_available():
                    continue
                spec = catalog.spec
                galaxies = catalog.in_box(**viewport)
                if len(galaxies) == 0:
                    notes.append(f"{spec.name}: no galaxies in view")
                    continue
                by_id = "OBJECT_ID" in spec.columns
                try:
                    if by_id:
                        result = match_by_id(galaxies, self.catred_handler, data)
                    else:
                        result = match_by_position(
                            galaxies,
                            self.catred_handler,
                            data,
                            radius_arcsec,
                            catred_masked,
                            threshold,
                            maglim,
                        )
                except Exception as e:
                    logger.opt(exception=e).error(
                        f"Catalog '{spec.name}': CATRED match failed: {e}"
                    )
                    notes.append(f"{spec.name}: failed ({e})")
                    continue
                if result is None:
                    notes.append(f"{spec.name}: no CATRED sources loaded here")
                    continue
                write_matches(spec, result.rows)
                idx = result.display_matched_idx
                if len(idx) == 0:
                    notes.append(
                        f"{spec.name}: none of {len(galaxies)} OBJECT_IDs found in CATRED"
                        if by_id
                        else f"{spec.name}: none within {radius_arcsec}″ of {len(galaxies)} galaxies "
                        f"(nearest {result.overall_nearest_arcsec:.1f}″)"
                    )
                    continue
                self._store_click_data(spec, result, galaxies)
                hover = format_catred_hover(result.catred_scatter, idx, f"CATRED near {spec.name}")
                z = spec_z_values(galaxies, result.display_galaxy_idx, len(idx)).get("spec_z")
                if z is not None:
                    hover = [
                        h if v is None else f"{h}<br>{spec.name} z_spec: {v:.4f}"
                        for h, v in zip(hover, z)
                    ]
                traces.append(
                    build_match_trace(spec, result.catred_ra[idx], result.catred_dec[idx], hover)
                )
                if by_id:
                    summary = f"{len(idx)} of {len(galaxies)} galaxies found by OBJECT_ID"
                else:
                    summary = f"{len(idx)} CATRED sources within {radius_arcsec}″ of {len(galaxies)} galaxies"
                notes.append(f"{spec.name}: {summary}")
                logger.info(f"Catalog '{spec.name}': {summary} in view")

            categorized = TraceRegistry.extract_all_preserved(
                figure, exclude={TraceType.CATALOG_MATCH}
            )
            categorized[TraceType.CATALOG_MATCH] = traces
            figure["data"] = TraceRegistry.assemble_in_layer_order(categorized)
            return figure, "; ".join(notes)
