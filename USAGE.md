# Cluster Visualization - Quick Usage Guide

## 🔧 Prerequisites

**REQUIRED**: Activate EDEN-3.1 environment before using any tools:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

## 🎯 Standalone HTML Generator

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

### 2. Standalone HTML Generation
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
python generate_standalone_html.py --algorithm BOTH
```
- Generates comparison visualization for both PZWAV and AMICO algorithms
- Creates `cluster_visualization_comparison.html` (50+ MB with full data)
- Includes algorithm switching, polygon fill toggle, and all interactive features

### 3. Universal Launcher
```bash
./launch.sh
```
- Interactive menu with all options including new Dash app
- Tests dependencies automatically
- Provides fallback options
- Generates HTML files as needed

### 4. Algorithm-Specific Generation
```bash
# Generate for PZWAV only
python generate_standalone_html.py --algorithm PZWAV

# Generate for AMICO only  
python generate_standalone_html.py --algorithm AMICO

# Custom output filename
python generate_standalone_html.py --algorithm BOTH --output my_viz.html
```

## 🎯 Current Features

| Feature | Status | Description |
|---------|--------|-------------|
| Algorithm Comparison | ✅ **Working** | Switch between PZWAV and AMICO algorithms |
| Standalone HTML | ✅ **Working** | Self-contained files, no server needed |
| Polygon Fill Toggle | ✅ **Working** | Toggle CORE polygon fill on/off |
| Interactive Controls | ✅ **Working** | Zoom, pan, aspect ratio, size adjustment |
| Performance Optimization | ✅ **Working** | Basic vs Detailed view modes |

## 🚀 Immediate Solution

**Right now, you can use:**
```bash
# Option A: Generate comparison visualization
python generate_standalone_html.py --algorithm BOTH

# Option B: Use the universal launcher
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

Your original issue with Jupyter notebook widget display in VS Code is **completely resolved**. The standalone HTML generator provides reliable, shareable, and feature-complete visualizations with algorithm comparison capabilities.
