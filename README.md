# Cluster Visualization

This directory contains an interactive web-based visualization solution for cluster detection data, providing a reliable replacement for Jupyter notebook FigureWidget functionality.

## 🔧 Environment Requirements

**Required Environment**: This tool requires the EDEN-3.1 scientific Python environment.

Before using any tools, activate the environment:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

This provides required packages: `astropy`, `plotly`, `pandas`, `numpy`, `shapely`

## 🛠 Current Solution: Interactive Dash Application

The interactive Dash application provides real-time visualizations that work reliably in any web browser with comprehensive controls and features.

## ✅ Available Solutions

1. **Interactive Dash App** (🆕 **RECOMMENDED**): Real-time interactive web application with algorithm switching
2. **Interactive Dash Application** (✅ **RELIABLE**): Provides real-time interactive web interface
3. **Simple HTTP Server** (✅ **FALLBACK**): Serves HTML files via built-in Python server

## Features

- **🆕 Render Button Control**: Manual rendering trigger for better performance control
- **Algorithm Comparison**: Switch between PZWAV and AMICO detection algorithms  
- **Interactive scatter plots** of merged detection catalog data
- **Polygon fill toggle** for CORE tile boundaries (Basic View only)
- **Zoom-based MER tile display** - MER tile polygons shown in Detailed View
- **Hover information** showing detailed cluster data
- **Tile boundary visualization** with LEV1 and CORE polygons
- **Color-coded tiles** for easy identification
- **Aspect ratio controls** for optimal viewing
- **Plot size adjustment** for different screen sizes
- **Responsive web interface** that works reliably across different browsers

## Files

### Main Application
- `cluster_dash_app.py` - **NEW**: Interactive Dash web application with real-time controls

### Launch Scripts
- `launch.sh` - Universal launcher script with dependency testing

### Configuration
- `requirements.txt` - Python dependencies (simplified)
- `README.md` - This documentation
- `USAGE.md` - Detailed usage instructions

## 🚀 Quick Start

### 1. Activate Environment
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

### 2. **NEW: Interactive Dash App** (Recommended)
```bash
./cluster_visualization/scripts/run_dash_app_venv.sh
# Launches web app at http://localhost:8050 with browser auto-open
# Features: Real-time algorithm switching, interactive controls
# Automatically sets up virtual environment with required packages
```

### 3. Universal Launcher
```bash
./launch.sh
# Interactive menu with Dash app and dependency testing
```

## Configuration

The application uses an INI-based configuration system for easy customization. The configuration specifies all data paths and settings.

### Quick Setup

1. **Automatic setup** (recommended):
   ```bash
   ./setup_config.sh
   ```
   This script will detect common paths and create a personalized `config_local.ini` file.

2. **Manual setup**:
   ```bash
   cp config_example.ini config_local.ini
   # Edit config_local.ini with your specific paths
   ```

3. **Test configuration**:
   ```bash
   python config.py
   ```

### Configuration Files

- `config.ini` - Default configuration (tracked in git)
- `config_local.ini` - Your personal configuration (gitignored, takes precedence)
- `config_example.ini` - Example with common configuration patterns

### Key Configuration Sections

- **`[paths]`** - All data directories and file locations
- **`[files]`** - Specific file and directory names for each algorithm

```bash
pip install -r requirements.txt
```

### Dependencies
- `plotly` - Interactive plotting library
- `pandas` - Data manipulation
- `numpy` - Numerical computations
- `astropy` - FITS file handling
- `shapely` - Geometric operations

## Data Requirements

The application expects the following data structure:
- Merged detection catalog XML and FITS files
- Individual detection files
- Catred file information CSV
- Catred polygons pickle file
- Custom utility modules (`myutils.py`, `colordefinitions.py`)

Make sure all data paths in the code match your local file structure.

## Interactive Features

### Algorithm Comparison
- **PZWAV vs AMICO**: Switch between detection algorithms using the algorithm buttons
- **Real-time switching**: Instantly compare results between algorithms
- **Data summary**: View cluster counts for each algorithm

### View Controls
- **Basic View**: Fast rendering with clusters and tile boundaries
- **Detailed View**: Complete view with MER tile polygons (comprehensive but slower)
- **Polygon Fill Toggle**: Turn CORE polygon fill on/off (Basic View only)

### Navigation
- **Mouse wheel**: Zoom in/out
- **Click and drag**: Pan around the plot
- **Reset Zoom**: Return to full data view
- **Aspect Ratio Toggle**: Switch between equal and free aspect ratios
- **Plot Size**: Adjust plot height (400px - 1200px)

### Data Exploration
- **Hover**: See detailed information about clusters and tiles
- **Legend**: Click items to hide/show specific data series
- **Color coding**: Each tile has a unique color for easy identification

## Troubleshooting

### Dependency Issues
If you see import errors, install the requirements:
```bash
pip install -r requirements.txt
```

### Data File Errors
Check that all data files exist in the expected locations:
- `/sps/euclid/OU-LE3/CL/ial_workspace/workdir/MergeDetCat/RR2_south/`
- `/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads/`

### Custom Module Errors
Ensure the custom modules are in the expected location:
- `/pbs/home/v/vnistane/mypackage/myutils.py`
- `/pbs/home/v/vnistane/mypackage/colordefinitions.py`

### Large File Sizes
The Dash application provides interactive visualizations with comprehensive features:
- Use Simple HTTP Server for better performance
- Consider using Basic View for faster loading
- MER tiles add significant size to files

## Advantages over Jupyter Notebook

1. **Reliable rendering**: No issues with widget display in VS Code
2. **Better performance**: Optimized for web browsers
3. **Shareable**: Easy to share with colleagues via file or URL
4. **Responsive**: Works on different screen sizes
5. **Self-contained**: Standalone HTML works without server requirements
6. **Better interactivity**: More responsive zoom and pan operations
7. **Algorithm comparison**: Easy switching between PZWAV and AMICO
8. **Production ready**: Can be deployed as a web service

## Visualization Features

The standalone HTML visualization includes:

- **Algorithm comparison mode**: PZWAV and AMICO side-by-side comparison
- **Two viewing modes**:
  - Basic View: Fast rendering with clusters and tile boundaries
  - Detailed View: Complete view with MER tile polygons (slower but comprehensive)
- **Interactive controls**: Algorithm switching, view mode, polygon fill toggle
- **Performance optimized**: Start with basic view for overview, detailed view for specifics
- **Fully self-contained**: No server required, works offline
- **Data summary**: Shows cluster counts, tile information for both algorithms
- **Color-coded visualization**: Each tile has unique colors for identification

## Data Visualization Details

The visualization displays:
- **PZWAV**: 7,437 merged clusters from 11 individual tiles
- **AMICO**: 25,843 merged clusters from 11 individual tiles  
- **1,935 MER tile polygons** (shown in detailed view)
- **LEV1 and CORE polygons** for each tile
- **Interactive hover information** with detailed cluster data
- **Algorithm-specific styling**: Different markers and colors for easy distinction

## Development

To modify the application:

1. Edit `cluster_dash_app.py` for functionality changes
2. Update `requirements.txt` if adding new dependencies  
3. Modify data paths in the `load_data()` function as needed
4. Test locally by running the Dash application
5. Use the launcher script to verify all functionality

The application uses Plotly's Scattergl for better performance with large datasets and supports both algorithm comparison and individual algorithm views.
