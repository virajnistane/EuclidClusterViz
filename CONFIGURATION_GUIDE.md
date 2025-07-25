# Configuration Guide for Cluster Visualization

## Overview

The Cluster Visualization tools now use a centralized configuration system for improved portability across different users and environments. This eliminates hardcoded paths and makes it easy to adapt the tools to different computing environments.

## Quick Setup

### 1. Run the Environment Setup Script

```bash
cd /path/to/ClusterVisualization
./setup_environment.sh
```

This interactive script will:
- Check your current configuration
- Allow you to update paths for your environment
- Validate that all paths exist
- Provide next steps

### 2. Manual Configuration

If you prefer to configure manually, edit `config.py`:

```python
# Base configuration - modify these paths for your environment
self._base_workspace = '/your/euclid/workspace/path'
self._cvmfs_eden_path = '/your/cvmfs/eden/path'
self._user_home = '/your/home/directory'
```

### 3. Environment Variables (Alternative)

You can also use environment variables:

```bash
export EUCLID_WORKSPACE="/your/workspace/path"
export EDEN_PATH="/your/eden/path"
export USER_HOME="/your/home/path"
```

Then use `ConfigFromEnv` in your scripts.

## Configuration Files

### `config.py`
Main configuration file containing:
- **Base paths**: workspace, EDEN environment, user home
- **Derived paths**: data directories, output directories
- **Path validation**: checks that critical paths exist
- **Algorithm-specific paths**: output directories, detection file lists

### `setup_environment.sh`
Interactive setup script that:
- Detects current environment
- Prompts for path customization
- Updates configuration automatically
- Validates the setup

## Using the Configuration

### In Jupyter Notebooks

```python
# Import configuration at the beginning of your notebook
from config import get_config, validate_environment, setup_environment_paths

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
   ./setup_environment.sh
   # Update paths to match your environment
   ```

2. **Import errors**:
   ```python
   # Check Python path setup
   from config import setup_environment_paths
   setup_environment_paths()
   ```

3. **EDEN environment not found**:
   ```bash
   # Activate EDEN environment
   source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
   ```

### Fallback Behavior

If configuration fails, tools fall back to hardcoded paths:
- Dash app continues with original paths
- Clear warnings are displayed
- Functionality is preserved

## Examples

### Different User Setup

User on different system:
```python
# In config.py, update these lines:
self._base_workspace = '/data/euclid/workspace'
self._user_home = '/home/researcher'
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
