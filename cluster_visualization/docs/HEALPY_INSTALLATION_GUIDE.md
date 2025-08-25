# New User Setup Guide - Healpy Installation Issue

## Quick Fix for "No module named 'healpy'" Error

If you're encountering the error "Error importing data modules: No module named 'healpy'", here's how to fix it:

### Option 1: Automatic Fix (Recommended)
The updated run script now automatically detects and installs missing dependencies:

```bash
# Use the Dash app launcher which will auto-install missing packages
bash cluster_visualization/scripts/run_dash_app_venv.sh
```

The script will:
- ✅ Check for healpy and install it if missing
- ✅ Verify all other dependencies
- ✅ Install any missing packages automatically
- ✅ Launch the application

### Option 2: Manual Installation

If you prefer to install manually or the automatic fix doesn't work:

```bash
# Activate your virtual environment first
source venv/bin/activate

# Install healpy specifically
pip install "healpy>=1.16.0"

# Or install all requirements
pip install -r requirements.txt
```

### Option 3: Complete Fresh Setup

If you're a completely new user:

```bash
# Run the complete setup script
bash setup_venv.sh

# Then launch the app
bash cluster_visualization/scripts/run_dash_app_venv.sh
```

## Why Healpy is Required

Healpy is used for:
- 🗺️ **HEALPix operations** - Processing astronomical survey data in HEALPix format
- 📊 **CATRED data handling** - Managing photometric redshift data
- 🔍 **Spatial operations** - Converting between coordinate systems and handling sky coverage

## Checking Your Installation

Test if everything is working:

```bash
# Run the dependency test
bash cluster_visualization/scripts/launch.sh
# Choose option 2 to test dependencies
```

You should see:
```
✓ healpy OK
✓ All dependencies working correctly
```

## Troubleshooting

### If healpy installation fails:

1. **Check your Python version**: Healpy requires Python 3.7+
   ```bash
   python --version
   ```

2. **Update pip and try again**:
   ```bash
   pip install --upgrade pip
   pip install "healpy>=1.16.0"
   ```

3. **System dependencies**: On some systems you may need:
   ```bash
   # On Ubuntu/Debian:
   sudo apt-get install python3-dev
   
   # On RHEL/CentOS:
   sudo yum install python3-devel
   ```

### If you still get import errors:

1. **Verify your virtual environment**:
   ```bash
   which python  # Should point to your venv
   echo $VIRTUAL_ENV  # Should show your venv path
   ```

2. **Check Python path**:
   ```bash
   python -c "import sys; print(sys.path)"
   ```

3. **Try importing directly**:
   ```bash
   python -c "import healpy; print('Success!')"
   ```

## What's New in the Updated Scripts

### Enhanced run_dash_app_venv.sh:
- ✅ Automatic healpy detection and installation
- ✅ Missing dependency resolution
- ✅ Better error messages with solutions
- ✅ Graceful handling of installation failures

### Enhanced launch.sh:
- ✅ Healpy included in dependency tests
- ✅ Clear indication when healpy is missing
- ✅ Better guidance for resolution

### Enhanced CATRED handler:
- ✅ Clear error message when healpy is missing
- ✅ Installation instructions in the error message

## For System Administrators

If you're setting up the application for multiple users:

1. **Pre-install healpy system-wide**:
   ```bash
   pip install healpy>=1.16.0
   ```

2. **Or ensure requirements.txt is used**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify EDEN environment includes healpy**:
   ```bash
   module load <appropriate-healpy-module>
   ```

The application now handles missing dependencies gracefully and provides clear instructions for resolution.
