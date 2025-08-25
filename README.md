# Cluster Visualization

This directory contains an interactive web-based visualization solution for cluster detection data, providing a reliable replacement for Jupyter notebook FigureWidget functionality with advanced remote access capabilities.

## 🔧 Environment Requirements

**Required Environment**: This tool requires the EDEN-3.1 scientific Python environment.

Before using any tools, activate the environment:
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

This provides required packages: `astropy`, `plotly`, `pandas`, `numpy`, `shapely`

## 🛠 Current Solution: Interactive Dash Application

The interactive Dash application provides real-time visualizations that work reliably in any web browser with comprehensive controls and features. Now includes **SSH tunnel connection monitoring** for seamless remote access.

## ✅ Available Solutions

1. **Interactive Dash App** (🆕 **RECOMMENDED**): Real-time interactive web application with algorithm switching and SSH tunnel monitoring
2. **Interactive Dash Application** (✅ **RELIABLE**): Provides real-time interactive web interface
3. **Simple HTTP Server** (✅ **FALLBACK**): Serves HTML files via built-in Python server

## 🆕 New Features

### SSH Tunnel Connection Monitoring
- **Automatic connection detection**: Monitors if users have properly connected via SSH tunnel
- **Smart warnings**: Alerts users if no connections detected within 2 minutes
- **Step-by-step guidance**: Provides exact SSH tunnel commands with actual hostname
- **Connection validation**: Confirms when SSH tunnel is working correctly

### Enhanced CATRED Data Support
- **Masked CATRED data**: Advanced sparse HEALPix mask handling (NSIDE=16384)
- **Comparison modes**: Switch between unmasked, masked, and comparison views
- **PHZ PDF plots**: Interactive photometric redshift probability plots from CATRED clicks

## Features

- **🆕 SSH Tunnel Monitoring**: Automatic detection and guidance for remote access setup
- **🆕 Masked CATRED Integration**: Advanced sparse HEALPix data handling with comparison modes
- **🆕 PHZ PDF Plotting**: Interactive photometric redshift visualization
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
- `cluster_visualization/src/cluster_dash_app.py` - **MAIN**: Interactive Dash web application with SSH monitoring
- `cluster_visualization/core/app.py` - Core application management with connection monitoring

### Modular Components
- `cluster_visualization/src/data/` - Data loading and CATRED handling modules
- `cluster_visualization/src/visualization/` - Plotting and figure management
- `cluster_visualization/callbacks/` - Dash callback handlers
- `cluster_visualization/ui/` - User interface layout components
- `cluster_visualization/utils/` - Utility functions and color definitions

### Launch Scripts
- `launch.sh` - Universal launcher script with dependency testing
- `cluster_visualization/scripts/` - Various launch and setup scripts

### Configuration
- `config.ini` - Default configuration
- `config_local.ini` - Personal configuration (gitignored)
- `requirements.txt` - Python dependencies
- `README.md` - This documentation
- `docs/SSH_TUNNEL_MONITORING.md` - Detailed SSH tunnel monitoring documentation
- `USAGE.md` - Detailed usage instructions

## 🚀 Quick Start

### 1. Activate Environment
```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
```

### 2. **NEW: Interactive Dash App** (Recommended)
```bash
./launch.sh
# Universal launcher with dependency testing and virtual environment setup
# Launches web app at http://localhost:8050 with browser auto-open
# Features: Real-time algorithm switching, SSH tunnel monitoring, CATRED data
```

### 3. **Remote Access Setup**
When running on a remote server, the app automatically provides SSH tunnel guidance:

```bash
# The app will display these instructions:
🔗 SSH TUNNEL REQUIRED:
   This app runs on a remote server. To access it:
   1. Open a NEW terminal on your LOCAL machine
   2. Run: ssh -L 8050:localhost:8050 username@hostname
   3. Keep that SSH connection alive
   4. Open browser to: http://localhost:8050
```

**Connection Monitoring**: The app automatically detects if you've connected properly and warns if SSH tunnel setup is needed.

### 4. Alternative Launch Methods
```bash
# Direct script execution
./cluster_visualization/scripts/run_dash_app_venv.sh

# Manual Python execution (after EDEN activation)
python cluster_visualization/src/cluster_dash_app.py
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
- `healpy` - HEALPix operations for masked CATRED data
- `dash` - Web application framework
- `dash-bootstrap-components` - Enhanced UI components

## Remote Access & SSH Tunneling

### Automatic SSH Tunnel Detection
The application includes built-in monitoring to help users set up SSH tunneling correctly:

#### ✅ **What you'll see when starting the app:**
```
🔗 SSH TUNNEL REQUIRED:
   This app runs on a remote server. To access it:
   1. Open a NEW terminal on your LOCAL machine
   2. Run: ssh -L 8050:localhost:8050 username@hostname
   3. Keep that SSH connection alive
   4. Open browser to: http://localhost:8050
```

#### ✅ **Successful connection confirmation:**
```
✓ User successfully connected at 09:02:31
  ✓ SSH tunnel appears to be working correctly
  Browser: Mozilla/5.0 (...)
  Connection from: 127.0.0.1
```

#### ⚠️ **Automatic warnings (after 1 minute with no connections):**
```
⚠️  WARNING: No users have connected yet!
   App has been running for 1.0 minute

🔗 REQUIRED: SSH Tunnel Setup
   This app runs on a remote server and requires SSH tunneling.
   
   1. Open a NEW terminal on your LOCAL machine
   2. Run this command:
      ssh -L 8050:localhost:8050 username@hostname
   3. Keep that SSH connection alive
   4. Open your browser to: http://localhost:8050
```

### Benefits
- **Reduces support requests**: Clear instructions prevent common SSH setup errors
- **Faster troubleshooting**: Immediate feedback if connection setup is incorrect  
- **Better user experience**: Step-by-step guidance for remote access
- **Automatic detection**: No manual intervention required

## Data Requirements

The application expects the following data structure:
- Merged detection catalog XML and FITS files
- Individual detection files
- Catred file information CSV
- Catred polygons pickle file
- Custom utility modules (`myutils.py`, `colordefinitions.py`)

Make sure all data paths in the code match your local file structure.

## Interactive Features

### SSH Tunnel Connection Monitoring
- **Real-time detection**: Monitors if users have properly connected via SSH tunnel
- **Automatic warnings**: Alerts users after 1 minute if no connections detected
- **Connection validation**: Confirms when SSH tunnel is working correctly
- **Hostname detection**: Provides exact SSH commands with actual server hostname

### CATRED Data Integration
- **Masked vs Unmasked**: Compare masked and unmasked CATRED data
- **Sparse HEALPix Support**: Advanced handling of NSIDE=16384 sparse format
- **PHZ PDF Plots**: Click on CATRED points to view photometric redshift probability distributions
- **Interactive Comparison**: Switch between different CATRED data modes

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

### SSH Tunnel Issues
If you can't connect to the app:
1. **Check the SSH tunnel command**: The app displays the exact command needed
2. **Verify the tunnel is active**: Make sure your SSH connection is still alive
3. **Check for port conflicts**: Try a different port if 8050 is busy
4. **Browser connection**: Ensure you're accessing `http://localhost:8050` (not the server IP)

### Connection Monitoring Messages
- **No warnings**: SSH tunnel is working correctly
- **Warning after 2 minutes**: Follow the displayed SSH tunnel setup instructions
- **Connection confirmed**: You should see "✓ User successfully connected" message

### Dependency Issues
If you see import errors, install the requirements:
```bash
pip install -r requirements.txt
```

### CATRED Data Issues
If CATRED data features don't work:
```bash
# Install HEALPix support
pip install healpy
```

### Data File Errors
Check that all data files exist in the expected locations:
- `/sps/euclid/OU-LE3/CL/ial_workspace/workdir/MergeDetCat/RR2_south/`
- `/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads/`

### Custom Module Errors
Ensure the custom modules are in the expected location:
- Check the `cluster_visualization/utils/` directory for utility modules
- Verify configuration paths in `config.ini`

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
9. **🆕 Remote access support**: Built-in SSH tunnel monitoring and guidance
10. **🆕 Advanced data integration**: CATRED masked data support with PHZ plotting
11. **🆕 Connection monitoring**: Automatic detection of user connectivity issues
12. **🆕 User guidance**: Step-by-step instructions for remote access setup

## Recent Improvements

### SSH Tunnel Connection Monitoring (August 2025)
- Automatic detection of user connections via SSH tunnel
- Real-time warnings if no connections detected within 2 minutes
- Exact SSH tunnel commands with actual hostname detection
- Connection validation and success confirmation

### CATRED Data Enhancement (August 2025)
- Masked CATRED data support with sparse HEALPix format (NSIDE=16384)
- Interactive PHZ PDF plots from CATRED point clicks
- Comparison modes between masked and unmasked data
- Advanced data handling with healpy integration

### Infrastructure Improvements (August 2025)
- Simplified configuration system without utils_dir dependencies
- Enhanced modular architecture with fallback support
- Improved error handling and user feedback
- Better path resolution and dependency management

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

1. **Main functionality**: Edit `cluster_visualization/src/cluster_dash_app.py` for core application changes
2. **SSH monitoring**: Modify `cluster_visualization/core/app.py` for connection monitoring features
3. **Data handling**: Update modules in `cluster_visualization/src/data/` for CATRED and loading logic
4. **Visualization**: Modify `cluster_visualization/src/visualization/` for plotting and figure management
5. **UI components**: Edit `cluster_visualization/ui/` for layout and interface changes
6. **Dependencies**: Update `requirements.txt` if adding new packages
7. **Configuration**: Modify `config.ini` for data paths and settings
8. **Testing**: Use `./launch.sh` to verify all functionality

### Architecture Overview
- **Modular design**: Separated concerns with dedicated modules for data, visualization, UI, and callbacks
- **Fallback support**: Robust fallback mechanisms when modular components aren't available
- **Configuration-driven**: Easy path management through INI-based configuration
- **Connection monitoring**: Built-in SSH tunnel detection and user guidance
- **Performance optimized**: Uses Plotly's Scattergl for large datasets

### Key Technologies
- **Dash + Plotly**: Interactive web application framework with high-performance plotting
- **HEALPix**: Advanced sparse format support for astronomical data (NSIDE=16384)
- **Flask middleware**: Custom connection tracking and SSH tunnel validation
- **Background monitoring**: Non-intrusive connection status checking
- **Modular callbacks**: Organized callback system for maintainable code

The application supports both algorithm comparison and individual algorithm views with comprehensive CATRED data integration and remote access monitoring.
