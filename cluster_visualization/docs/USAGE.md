# Cluster Visualization - Quick Usage Guide

## 🔧 Prerequisites

**REQUIRED**: Activate EDEN-3.1 environment before using any tools:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

**Remote Access**: The app assigns each user a personal port automatically. The exact `ssh -L` tunnel command is printed at startup. See [Quick Remote Access Setup](https://github.com/virajnistane/EuclidClusterViz/blob/main/README.md#quick-remote-access-setup).

## 🎯 Interactive Dash Application

**Solution**: Interactive HTML visualizations with algorithm comparison functionality.

## ✅ USAGE METHODS

### 1. **NEW: Interactive Dash App** (Recommended)
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
./cluster_visualization/scripts/run_dash_app_venv.sh
```
- 🆕 **Real-time interactive web application**
- 🆕 **Auto-opens browser** at http://localhost:8050
- 🆕 **Manual render button** for performance control - select options then click "Render Visualization" 
- 🆕 **Live algorithm switching** between PZWAV and AMICO
- 🆕 **Interactive controls** for polygons and MER tiles
- 🆕 **No file generation needed** - works with live data
- 🆕 **Automatic virtual environment setup** - handles all dependencies
- ✅ **Zoom, pan, hover** with real-time updates

### 2. Universal Launcher
```bash
./launch.sh
```
- Interactive menu with all options including new Dash app
- Tests dependencies automatically
- Provides fallback options
- Provides interactive web interface

### 4. Algorithm-Specific Generation
```

## 🎯 Current Features

| Feature | Status | Description |
|---------|--------|-------------|
| Algorithm Comparison | ✅ **Working** | Switch between PZWAV, AMICO, and BOTH algorithms |
| Cluster Matching | ✅ **Working** | Visual matching of PZWAV-AMICO pairs (BOTH mode) |
| Cluster Analysis Tab | ✅ **Working** | Cutouts, CATRED boxes, mask overlays |
| Trace Management | ✅ **Working** | Hide/show and clear controls for all overlays |
| Interactive Dash App | ✅ **Working** | Real-time controls, tabbed interface |
| CATRED Integration | ✅ **Working** | High-resolution catalog with PHZ analysis |
| Mosaic Overlays | ✅ **Working** | Background images and mask visualization |
| Polygon Fill Toggle | ✅ **Working** | Toggle CORE polygon fill on/off |
| CL-tile Information Toggle | ✅ **NEW** | Color clusters by tile; optionally show MER tile polygons |
| Interactive Controls | ✅ **Working** | Zoom, pan, aspect ratio, size adjustment |
| Performance Optimization | ✅ **Working** | Client-side filtering, tile caching, smart rendering |
| Viewport Zoom Indicator | ✅ **NEW** | Real-time zoom level display with rendering guidance |

## 🚀 Immediate Solution

**Right now, you can use:**
```bash
# Interactive Dash app via launcher
./launch.sh
```

All methods provide comprehensive visualization with:
- ✅ **Algorithm Comparison**: PZWAV (7,437 clusters) vs AMICO (25,843 clusters) vs BOTH
- ✅ **Cluster Matching**: Visual indication of matched PZWAV-AMICO pairs
- ✅ **Cluster Analysis**: Dedicated tab for cutouts, CATRED boxes, and mask overlays
- ✅ **CATRED Integration**: High-resolution catalog with PHZ probability plots
- ✅ **Cluster-ID Upload Filtering**: Upload `.txt`, `.dat`, or `.csv` files to constrain merged-catalog views; multi-column `.dat` files use the first column as the ID list
- ✅ **Mosaic & Mask Overlays**: Background images and coverage visualization
- ✅ **Trace Management**: Independent control of all overlay layers
- ✅ **Interactive Controls**: Zoom, pan, polygon fill toggle, aspect ratio
- ✅ **Tile Information Control**: Toggle to show/hide tile coloring and MER tile polygons
- ✅ **Smart Filtering**: Client-side SNR and redshift filtering
- ✅ **PHZ Cluster Data Filtering**: PHZ cluster-data plots follow the same algorithm, viewport, SNR, redshift, and uploaded ID constraints as the current view
- ✅ **Hover Information**: Detailed cluster, tile, and catalog data with optional tile IDs
- ✅ **Color-coded Tiles**: Each tile has unique colors for identification (when enabled)
- ✅ **Viewport Zoom Guidance**: Real-time indicator showing zoom level and rendering readiness for matched clusters

## Notes on Current Behavior

- The CATRED render button is enabled only when MER tiles are shown and the current plot window is zoomed to less than 2 degrees in both RA and Dec.
- The CATRED zoom check uses the current plot layout as a fallback when Plotly emits partial `relayoutData`, so switching between pan and zoom tools should no longer incorrectly disable the button.

## 🆕 Recent UI Improvements

### CL-tile Information Toggle

Located in the **Merged Clusters** section:
- **Enabled by default** — shows tile-based colors and MER tile polygons
- **Disable to improve performance** — removes MER tile polygon rendering (O(9 × 366ms) per render)
- When disabled: clusters use flat algorithm colors (PZWAV: royal blue, AMICO: tomato) and hover shows `Cluster (PZWAV)` without tile suffix
- **Tile Definition Caching**: Tile metadata is cached in memory after first load to eliminate repeated JSON file reads

### Viewport Zoom Indicator

Real-time indicator in the **Matched Clusters** section shows current zoom level and rendering readiness:

| State | Display | Meaning |
|-------|---------|---------|
| Ready | ✓ 2.1° × 1.8° — ready to render ovals | < 5° max dimension; safe to render |
| Caution | ⚠ 8.3° × 6.1° — zoom in for fewer ovals | 5–15° max dimension; slow but possible |
| Too Wide | ✗ 42.0° × 35.0° — too wide, zoom in first | > 15° max dimension; will limit to 2000 ovals |

Updates in real-time as you zoom/pan, no server calls needed.

## 📖 Detailed Feature Guides

For in-depth information on specific features:
- **[Cluster Analysis](CLUSTER_ANALYSIS_GUIDE.md)** - Cutouts, CATRED boxes, mask overlays, trace management
- **[Configuration](CONFIGURATION_GUIDE.md)** - Setup and configuration options
- **[Tile Caching & Controls](TILE_CACHING_AND_CONTROLS.md)** - CL-tile toggle, tile definition caching, performance
- **[Zoom-Based Oval Rendering](ZOOM_BASED_OVAL_RENDERING.md)** - Matched cluster rendering with viewport indicator
- **[Remote Access](https://github.com/virajnistane/EuclidClusterViz/blob/main/README.md#quick-remote-access-setup)** - SSH port forwarding setup

## 🎉 Problem Solved

Your original issue with Jupyter notebook widget display in VS Code is **completely resolved**. The Dash app provides reliable, interactive visualizations with comprehensive algorithm comparison capabilities.

---

## Using Aladin Lite View

The Aladin Lite view replaces the Plotly scatter plot with a real sky image renderer (Aladin Lite v3, loaded from CDN). Cluster catalog entries and CATRED sources are overlaid as clickable markers on top of the sky survey.

### Step-by-step walkthrough

**Step 1 — Select exactly 1 cluster on the main plot**

Zoom into the Plotly scatter plot until exactly **one cluster** falls within the viewport. The Aladin View button in the header (`view-mode-aladin-btn`) is disabled by default and becomes enabled only when the viewport-cluster-count reaches 1. The button tooltip reads *"Zoom to exactly 1 cluster to enable Aladin view"*.

**Step 2 — Click the "Aladin View" button in the header**

Click the **Aladin View** button in the toggle group at the top of the page. The Plotly container (`plotly-view-container`) is hidden and the Aladin container (`aladin-view-container`) is shown. A skeleton loading animation appears while Aladin Lite initialises.

Alternatively, switch the **Image Source** radio selector (in the Mosaic sidebar) from *MER Mosaic* to *Aladin Sky* — this achieves the same mode switch.

**Step 3 — Pick a sky survey from the dropdown**

Once in Aladin mode, a survey dropdown (`aladin-survey-dropdown`) appears in the Mosaic sidebar. Available surveys:

| Label | HiPS identifier |
|-------|----------------|
| DSS2 Color | `P/DSS2/color` |
| Euclid VIS Q1 | `CDS/P/Euclid/Q1/VIS` |
| Euclid NIR Q1 (color) | `CDS/P/Euclid/Q1/NIR` |
| 2MASS H | `P/2MASS/H` |
| WISE W1 | `P/allWISE/color` |

The survey value is read as a `State` by `push_overlay_data`, so it is captured on the next overlay refresh (mode switch, viewport change, or CATRED-ready event) rather than triggering an immediate reload by itself.

**Step 4 — Apply SNR / redshift filters**

The SNR range sliders (`snr-range-slider-pzwav`, `snr-range-slider-amico`) and the redshift range slider (`redshift-range-slider`) are wired as `State` inputs (not `Input` triggers) to the server-side `push_overlay_data` callback in `aladin_callbacks.py`. This means the overlay re-pushes whenever the mode switches to `"aladin"`, the viewport cluster count changes, or a CATRED render completes — and the current slider values are captured at that moment. To force an overlay refresh after adjusting filters, switch away from Aladin mode and back.

Cluster entries in the overlay payload include `SNR` and `Z` fields so that the JS bridge can display them in a popup when a source is clicked.

**Step 5 — Click sources in Aladin to select/inspect them**

Clicking a source marker in the Aladin view fires a clientside event that writes to `aladin-click-store`. The `aladin-click-poll-interval` (500 ms, enabled only in Aladin mode) polls that store and exposes the selected source's metadata (cluster ID, SNR, redshift) in the sidebar.

---

## Using ESA Sky View

ESA Sky is an alternative sky viewer provided by ESA, embedded as an iframe. It displays the same cluster and CATRED catalog overlays as the Aladin view, plus HEALPix mask tile centroids.

### How to activate

ESA Sky mode is activated by setting `view-mode-store` to `"esasky"`. The current production UI (header toggle and Image Source radio) only exposes `"plotly"` and `"aladin"` as options; ESA Sky mode can be triggered programmatically or via a custom extension of the view-mode toggle.

### What the iframe shows

When `view-mode-store` equals `"esasky"`, the server-side callback in `esasky_callbacks.py` (`push_overlay_data`) builds a JSON payload containing:

- **`clusters`** — all merged-catalog entries for the selected algorithm, each with `ra`, `dec`, `name` (cluster ID), `SNR`, and `Z` fields.
- **`catred`** — CATRED source positions (`ra`, `dec`) currently loaded in the sidebar.
- **`mask`** — centroid RA/Dec for each loaded HEALPix mask tile (from `mosaic_handler.traces_cache`).
- **`viewport`** — RA/Dec centre and FOV derived from the current Plotly figure axes.

This payload is pushed to `esasky-overlay-data-store`. The clientside JS bridge in `ui_callbacks.py` reads the store and calls `postMessage` on the ESA Sky iframe to pan the view and add catalog overlays.

### Interaction model

ESA Sky runs entirely within its iframe; all pan/zoom and source inspection happens inside the iframe's own UI. The Dash app only controls the initial viewport and catalog overlay via `postMessage`. There are no Dash callbacks that read back click events from the ESA Sky iframe.

---

## Switching Image Source

The **Image Source** radio selector (`image-source-radio`, id) in the Mosaic sidebar controls which background renderer is used in the main view area.

| Radio value | Effect |
|-------------|--------|
| `mosaic` | Standard Plotly scatter view; MER mosaic and HEALPix mask overlays are available via the sidebar controls below. The `mer-mosaic-controls` div is shown. |
| `aladin` | Switches to Aladin Lite view (same as clicking the Aladin View header button). The MER mosaic controls div is hidden; the survey dropdown is shown instead. |

When `mosaic` is selected the `aladin-survey-dropdown` is hidden (`display: none`). When `aladin` is selected, the `mer-mosaic-controls` wrapper div is hidden and the survey dropdown appears. Both transitions are handled client-side by the `view-mode-store` watcher callback in `ui_callbacks.py`, so no server round-trip is needed.
