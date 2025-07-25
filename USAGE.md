# Cluster Visualization - Quick Usage Guide

## 🔧 Prerequisites

**REQUIRED**: Activate EDEN-3.1 environment before using any tools:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

## 🎯 Standalone HTML Generator

**Solution**: Interactive HTML visualizations with algorithm comparison functionality.

## ✅ USAGE METHODS

### 1. Quick Start (Recommended)
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
python generate_standalone_html.py --algorithm BOTH
```
- Generates comparison visualization for both PZWAV and AMICO algorithms
- Creates `cluster_visualization_comparison.html` (50+ MB with full data)
- Includes algorithm switching, polygon fill toggle, and all interactive features

### 2. Universal Launcher
```bash
./launch.sh
```
- Interactive menu with multiple options
- Tests dependencies automatically
- Provides simple HTTP server option
- Generates HTML files as needed

### 3. Simple HTTP Server
```bash
python simple_server.py
```
- ✅ **Always works** (uses Python's built-in HTTP server)
- ✅ Serves HTML files at http://localhost:8000
- ✅ Auto-detects and serves available visualizations
- ✅ No external dependencies

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
| Simple HTTP Server | ✅ **Working** | Local web server for better performance |
| Polygon Fill Toggle | ✅ **Working** | Toggle CORE polygon fill on/off |
| Interactive Controls | ✅ **Working** | Zoom, pan, aspect ratio, size adjustment |
| Performance Optimization | ✅ **Working** | Basic vs Detailed view modes |

## 🚀 Immediate Solution

**Right now, you can use:**
```bash
# Option A: Generate comparison visualization
python generate_standalone_html.py --algorithm BOTH

# Option B: Use web server for better performance
python simple_server.py

# Option C: Use the universal launcher
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
