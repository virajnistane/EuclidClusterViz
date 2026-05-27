# Configuration Guide for Cluster Visualization

## Overview

The Cluster Visualization tools use an INI-based configuration system that makes it easy to adapt the tools to different computing environments. The configuration system supports user-specific settings, environment variables, and automatic path detection.

## Quick Setup

### 1. Automatic Configuration Setup

```bash
cd /path/to/ClusterVisualization
./setup_config.sh
```

This interactive script will:
- Detect common Euclid data paths automatically
- Prompt you for any missing paths
- Create a personalized `config_local.ini` file
- Test the configuration to ensure it works

### 2. Run the Application

```bash
./launch.sh
```

The launcher will:
- Automatically load your configuration
- Check and activate the EDEN environment
- Launch the Dash app directly (no interactive prompts)
- Handle all environment setup automatically

**Command-Line Options:**
```bash
./launch.sh --help              # Show all available options
./launch.sh --test-dependencies # Test environment without launching
./launch.sh --config FILE       # Use custom configuration file
```

### 3. Manual Configuration (Advanced)

If you prefer to configure manually:

```bash
# Copy the example configuration
cp config_example.ini config_local.ini

# Edit with your specific paths
nano config_local.ini

# Test the configuration
python config.py
```

## Configuration File Structure

### Configuration Files

The system uses three configuration files:

- **`config.ini`** - Default configuration (version controlled)
- **`config_local.ini`** - Your personal configuration (gitignored, highest priority)
- **`config_example.ini`** - Example configurations for reference

### Configuration Sections

#### `[paths]` - Data Locations
```ini
base_workspace = /sps/euclid/OU-LE3/CL/ial_workspace/workdir
eden_path = /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1
mergedetcat_dir = ${paths:base_workspace}/MergeDetCat/RR2_south
rr2_downloads_dir = ${paths:base_workspace}/RR2_downloads
```

#### `[files]` - File and Directory Names
```ini
# PZWAV algorithm files
pzwav_detfiles_list = detfiles_input_pzwav_3.json
pzwav_output_dir = outvn_mergedetcat_rr2south_PZWAV_3

# AMICO algorithm files  
amico_detfiles_list = detfiles_input_amico_3.json
amico_output_dir = outvn_mergedetcat_rr2south_AMICO_3

# Common files
catred_fileinfo_csv = catred_fileinfo.csv
catred_polygons_pkl = catred_polygons_by_tileid.pkl
```

### Variable Interpolation

The configuration system supports variable interpolation:
```ini
base_workspace = /data/euclid
mergedetcat_dir = ${paths:base_workspace}/MergeDetCat/RR2_south
```

Environment variables are also supported:
```ini
base_workspace = ${HOME}/euclid_data
eden_path = ${EDEN_PATH}
```

### Environment Variables (Alternative)

You can also use environment variables to override configuration:

```bash
export EUCLID_WORKSPACE="/your/workspace/path"
export EDEN_PATH="/your/eden/path"
```

Then use `ConfigFromEnv` in your scripts for environment variable priority.

## Using the Configuration

### In Jupyter Notebooks

```python
# Import configuration at the beginning of your notebook
from config import get_config, validate_environment

# Get configuration instance
config = get_config()

# Validate environment
is_valid, issues = validate_environment()

# Use configured paths
mergedetcatdir = config.mergedetcat_dir
output_dir = config.get_output_dir('PZWAV')
```

### In Dash App

The Dash app automatically detects and uses the configuration:

```python
# Automatic detection
if USE_CONFIG:
    # Uses config.py paths
    mergedetcatdir = config.mergedetcat_dir
else:
    # Falls back to hardcoded paths
    mergedetcatdir = '/sps/euclid/...'
```

### In Standalone Scripts

```python
from config import get_config

config = get_config()
data_dir = config.mergedetcat_data_dir
catred_files = config.get_catred_fileinfo_csv()
```

## Path Structure

The configuration system manages these key paths:

### Base Paths (User Configurable)
- **Base Workspace**: `/sps/euclid/OU-LE3/CL/ial_workspace/workdir`
- **EDEN Environment**: `/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1`
- **User Home**: `/pbs/home/v/vnistane`

### Derived Paths (Automatically Calculated)
- **MergeDetCat Directory**: `{base_workspace}/MergeDetCat/RR2_south/`
- **Data Directory**: `{mergedetcat_dir}/data`
- **Inputs Directory**: `{mergedetcat_dir}/inputs`
- **Downloads Directory**: `{base_workspace}/RR2_downloads`
- **CATRED Directory**: `{downloads_dir}/DpdLE3clFullInputCat`

### Algorithm-Specific Paths
- **Output Directory**: `{mergedetcat_dir}/outvn_mergedetcat_rr2south_{algorithm}_3`
- **Detection Files List**: `{mergedetcat_dir}/detfiles_input_{algorithm}_3.json`

## Migration from Hardcoded Paths

### Before (Hardcoded)
```python
mergedetcatdir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/MergeDetCat/RR2_south/'
rr2downloadsdir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads'
catreddir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads/DpdLE3clFullInputCat'
```

### After (Configurable)
```python
from config import get_config
config = get_config()

mergedetcatdir = config.mergedetcat_dir
rr2downloadsdir = config.rr2_downloads_dir
catreddir = config.catred_dir
```

## Environment Validation

The configuration system includes validation:

```python
from config import validate_environment

is_valid, issues = validate_environment()
if not is_valid:
    for issue in issues:
        print(f"❌ {issue}")
```

### Validation Checks
- ✅ Critical directories exist
- ✅ Data files are accessible
- ✅ EDEN environment is available
- ✅ Python path setup is correct

## Troubleshooting

### Configuration Issues

1. **Paths don't exist**:
   ```bash
   # Test your environment and see validation results
   ./launch.sh --test-dependencies
   
   # Edit config.py directly to update paths for your environment
   # The launcher will automatically detect and validate paths
   ./launch.sh
   ```

2. **Import errors**:
   ```python
   # Check Python path and configuration
   from config import get_config, validate_environment
   config = get_config()
   is_valid, issues = validate_environment()
   ```

3. **EDEN environment not found**:
   ```bash
   # Test dependencies and see environment status
   ./launch.sh --test-dependencies
   
   # The launcher will automatically activate EDEN environment
   ./launch.sh
   
   # Or manually activate:
   source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
   ```

### Fallback Behavior

If configuration fails, tools fall back to hardcoded paths:
- Dash app continues with original paths
- Clear warnings are displayed
- Functionality is preserved

## Launcher Options

### Available Commands

```bash
# Direct launch (recommended)
./launch.sh

# Show help and all options
./launch.sh --help

# Test environment without launching
./launch.sh --test-dependencies

# Use custom configuration file
./launch.sh --config /path/to/custom_config.ini

# Combine options
./launch.sh --config custom.ini --test-dependencies
```

### When to Use Each Option

- **Default launch** (`./launch.sh`): Normal use after initial setup
- **`--help`**: Discover all available options and usage examples
- **`--test-dependencies`**: Validate environment setup before launching
- **`--config FILE`**: Test different configurations or use project-specific settings

## Examples

### Different User Setup

User on different system:
```python
# In config.py, update these lines:
self._base_workspace = '/data/euclid/workspace'
self._cvmfs_eden_path = '/opt/euclid/eden'
```

### Using Environment Variables

```bash
export EUCLID_WORKSPACE="/custom/workspace/path"
python3 -c "
from config import ConfigFromEnv
config = ConfigFromEnv()
print(config.mergedetcat_dir)
"
```

### Testing Configuration

```python
# Test configuration validity
from config import get_config

config = get_config()
config.print_config_summary()

# Test specific algorithm
output_dir = config.get_output_dir('AMICO')
detfiles = config.get_detfiles_list('PZWAV')
```

## Benefits

✅ **Portability**: Easy adaptation to different environments  
✅ **Maintainability**: Single place to update paths  
✅ **Validation**: Automatic checks for missing files/directories  
✅ **Fallback**: Graceful degradation if configuration fails  
✅ **Documentation**: Clear understanding of required paths  
✅ **Flexibility**: Support for environment variables and custom setups

## Image Display Configuration

### Default Mosaic Source: `local_fits`

The default mosaic provider is now `local_fits` (previously `esa_sky`). When a cluster mosaic is requested, the app reads locally-stored Euclid MER FITS tiles from the path configured under `paths.mosaic_dir` in your INI file, rather than fetching data from the ESA HiPS service over the network.

This means:
- No external network access is required for mosaic images when using the default provider.
- The `paths.mosaic_dir` key must point to a directory containing `EUC_MER_BGSUB-MOSAIC-VIS_TILE{id}*.fits.gz` files.
- If local files are missing for a given tile, `MOSAICHandler` logs a warning and returns no image for that tile.

To revert to the ESA Sky (public HiPS) provider, select **ESA Sky (Public HiPS)** from the **Mosaic Source** dropdown in the sidebar, or configure the default in your `config_local.ini`:

```ini
[mosaic]
provider_default = esa_sky
```

The `MOSAICHandler` accepts the aliases `local`, `local_fits`, `fits`, `mer` (all map to `local_fits`) and `esa`, `esa_sky`, `esasky` (all map to `esa_sky`).

### Image Source Radio Selector

Location: **Mosaic / Image Source** card in the sidebar.

The `image-source-radio` control has two options:

| Value | Label | Effect |
|-------|-------|--------|
| `mosaic` | MER Mosaic | Shows the Plotly scatter plot with optional local-FITS or ESA-Sky mosaic overlays. All MER mosaic controls (`mer-mosaic-controls`) are visible. |
| `aladin` | Aladin Sky | Switches to the embedded Aladin Lite sky viewer centered on the selected cluster. The MER mosaic controls are hidden and the survey dropdown becomes visible. |

The **Aladin Sky** option is only enabled when exactly one cluster point is visible in the current zoom viewport. When zero or more than one cluster is in view the option is disabled automatically.

Selecting either option also syncs the top-level **Plotly / Aladin** toggle buttons in the main view area.

### Aladin Survey Dropdown

Location: **Mosaic / Image Source** card, visible only when **Aladin Sky** mode is active (`aladin-survey-dropdown`).

The dropdown is hidden in Mosaic mode (`style: {display: 'none'}`) and shown in Aladin mode (`style: {display: 'block'}`).

Available surveys:

| Label | HiPS identifier |
|-------|----------------|
| DSS2 Color | `P/DSS2/color` |
| Euclid VIS Q1 | `CDS/P/Euclid/Q1/VIS` |
| Euclid NIR Q1 (color) | `CDS/P/Euclid/Q1/NIR` |
| 2MASS H | `P/2MASS/H` |
| WISE W1 | `P/allWISE/color` |

The default survey is **DSS2 Color** (`P/DSS2/color`). Changing the dropdown value immediately reloads the Aladin viewer with the new HiPS layer for the currently selected cluster.
