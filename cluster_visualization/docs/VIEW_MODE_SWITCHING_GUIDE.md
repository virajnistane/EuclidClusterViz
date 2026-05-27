## View Mode Switching Guide

ClusterViz provides two visualization modes: **Standard (Plotly)** and **Aladin View**.
The toggle sits in the header above the main plot.

---

## The Toggle

`esasky_view.py → create_view_mode_toggle()` renders a `dbc.ButtonGroup` with two buttons:

| Button ID | Label | Default state |
|-----------|-------|---------------|
| `view-mode-plotly-btn` | Standard View | Active (outline=False) |
| `view-mode-aladin-btn` | Aladin View | Disabled, outline=True |

The active mode is persisted in `dcc.Store(id="view-mode-store", data="plotly")`.

A tooltip on `view-mode-aladin-btn` reads: *"Zoom to exactly 1 cluster to enable Aladin view"*.

---

## Standard Mode (Plotly)

Default mode. Renders the full interactive `dcc.Graph(id="cluster-plot")` scatter plot.

**Use it for:**
- Browsing the full catalog, filtering by SNR / redshift
- Clicking clusters to open the analysis modal
- Running CATRED box queries
- Loading MER mosaic tiles or HEALPix masks

The main plot occupies the left 8 columns. All sidebar controls (render button, filters,
mosaic/mask panel) apply to this mode.

---

## Aladin View Mode

Embeds the **Aladin Lite v3** sky viewer (`aladin_view.py → create_aladin_view()`).
The viewer container `#aladin-div` is hidden by default (`display: none`) and shown
when the user switches to Aladin mode.

### Enable condition

`view-mode-aladin-btn` is only enabled when **exactly 1 cluster** is in the current
viewport (`viewport-cluster-count-store`). This constraint exists because Aladin Lite
is centered on a single sky coordinate; multiple clusters would require manual
re-centering.

### What happens on switch

1. Clientside JS in `ui_callbacks.py` intercepts the button click.
2. Aladin Lite v3 JS/CSS are lazy-loaded from CDN on the first switch.
3. `A.aladin('#aladin-div', {survey: <selected_survey>, fov: <viewport_fov>})` is called.
4. The skeleton overlay (`#aladin-skeleton`) is shown until the sky tiles load.
5. Catalog overlay data (filtered by current SNR / redshift values) is pushed via
   `aladin-overlay-data-store`.

### Available surveys

Controlled by `aladin-survey-dropdown` (visible only in Aladin mode):

| Label | HiPS identifier |
|-------|----------------|
| DSS2 Color | `P/DSS2/color` |
| Euclid VIS Q1 | `CDS/P/Euclid/Q1/VIS` |
| Euclid NIR Q1 (color) | `CDS/P/Euclid/Q1/NIR` |
| 2MASS H | `P/2MASS/H` |
| WISE W1 | `P/allWISE/color` |

Default: **DSS2 Color**.

### SNR / redshift filter pass-through

Changing the SNR or redshift sliders in Standard mode updates
`aladin-overlay-data-store`, which triggers the clientside JS to redraw the catalog
overlay in Aladin without reloading the sky tiles.

### Skeleton loading overlay

`#aladin-skeleton` contains three `.skeleton-star` divs and a label "Loading sky view…".
It is shown (`display: block`) immediately on mode switch and hidden once Aladin fires
its `positionChanged` or `objectClicked` event, confirming the JS initialised.

If CDN access is blocked, the skeleton stays visible indefinitely. See
`TROUBLESHOOTING.md` → "Aladin Lite Viewer".

---

## Image Source Radio Selector

`data_controls.py` contains an `image-source-radio` with two values:

| Value | Effect |
|-------|--------|
| `mosaic` | Shows the Plotly graph with MER mosaic overlay controls visible |
| `aladin` | Switches to Aladin view; mosaic controls hidden, survey dropdown shown |

The `aladin` option is dynamically enabled/disabled by `ui_callbacks.py` based on
`viewport-cluster-count-store` (same single-cluster constraint as the header button).

Switching either the header toggle or this radio syncs both controls to the same state.

---

## Switching Back to Standard Mode

Click **Standard View** in the header toggle (or set the radio to `mosaic`).
The Aladin container is hidden, the Plotly graph is shown, and the survey dropdown
is hidden. The `view-mode-store` resets to `"plotly"`.
