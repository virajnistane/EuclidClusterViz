# Cluster Visualization - Quick Usage Guide

## 🔧 Prerequisites

**REQUIRED**: Activate EDEN-3.1 environment before using any tools:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

**Remote Access**: If accessing from a remote server, see [Quick Remote Access Setup](../../../README.md#-quick-remote-access-setup) for SSH port forwarding instructions.

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
| Interactive Controls | ✅ **Working** | Zoom, pan, aspect ratio, size adjustment |
| Performance Optimization | ✅ **Working** | Client-side filtering and smart caching |

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
- ✅ **Smart Filtering**: Client-side SNR and redshift filtering
- ✅ **PHZ Cluster Data Filtering**: PHZ cluster-data plots follow the same algorithm, viewport, SNR, redshift, and uploaded ID constraints as the current view
- ✅ **Hover Information**: Detailed cluster, tile, and catalog data
- ✅ **Color-coded Tiles**: Each tile has unique colors for identification

## Notes on Current Behavior

- The CATRED render button is enabled only when MER tiles are shown and the current plot window is zoomed to less than 2 degrees in both RA and Dec.
- The CATRED zoom check uses the current plot layout as a fallback when Plotly emits partial `relayoutData`, so switching between pan and zoom tools should no longer incorrectly disable the button.

## 📖 Detailed Feature Guides

For in-depth information on specific features:
- **[Cluster Analysis](CLUSTER_ANALYSIS_GUIDE.md)** - Cutouts, CATRED boxes, mask overlays, trace management
- **[Configuration](CONFIGURATION_GUIDE.md)** - Setup and configuration options
- **[Performance](PERFORMANCE_OPTIMIZATION_SUMMARY.md)** - Optimization details
- **[Remote Access](../../../README.md#-quick-remote-access-setup)** - SSH port forwarding setup

## 🎉 Problem Solved

Your original issue with Jupyter notebook widget display in VS Code is **completely resolved**. The Dash app provides reliable, interactive visualizations with comprehensive algorithm comparison capabilities.
