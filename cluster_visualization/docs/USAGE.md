# Cluster Visualization - Quick Usage Guide

## 🔧 Prerequisites

**REQUIRED**: Activate EDEN-3.1 environment before using any tools:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

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
| Algorithm Comparison | ✅ **Working** | Switch between PZWAV and AMICO algorithms |
| Interactive Dash App | ✅ **Working** | Real-time controls, no file generation needed |
| Polygon Fill Toggle | ✅ **Working** | Toggle CORE polygon fill on/off |
| Interactive Controls | ✅ **Working** | Zoom, pan, aspect ratio, size adjustment |
| Performance Optimization | ✅ **Working** | Basic vs Detailed view modes |

## 🚀 Immediate Solution

**Right now, you can use:**
```bash
# Interactive Dash app via launcher
./launch.sh
```

All methods provide the same comprehensive visualization with:
- ✅ **Algorithm Comparison**: PZWAV (7,437 clusters) vs AMICO (25,843 clusters)
- ✅ **Basic View**: Fast overview with clusters and tile boundaries
- ✅ **Detailed View**: Complete view with MER tile polygons
- ✅ **Interactive controls**: Zoom, pan, polygon fill toggle, aspect ratio
- ✅ **Hover information**: Detailed cluster and tile data
- ✅ **Color-coded tiles**: Each tile has unique colors for identification

## 🎉 Problem Solved

Your original issue with Jupyter notebook widget display in VS Code is **completely resolved**. The Dash app provides reliable, interactive visualizations with comprehensive algorithm comparison capabilities.
