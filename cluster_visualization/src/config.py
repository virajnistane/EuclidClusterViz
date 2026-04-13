#!/usr/bin/env python3
"""
Configuration file for Cluster Visualization tools

This file contains all user-specific paths and settings that need to be
configured for different users or environments.

The configuration is read from config.ini (or config_local.ini if it exists).
"""

import configparser
import os
import subprocess
from typing import Optional, List


def get_git_repo_root():
    """Get the root directory of the current git repository"""
    try:
        # Try to get the git repository root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback: assume config.py is in the project root
    return os.path.dirname(os.path.abspath(__file__))


class Config:
    """Configuration class for cluster visualization paths and settings"""

    def __init__(self, config_file=None):
        # Auto-detect project root from git repository
        self._detected_project_root = get_git_repo_root()

        # Load configuration from INI file
        self._load_config(config_file)

        # Validate and set up paths
        self._setup_paths()

    def _load_config(self, config_file=None):
        """Load configuration from INI file"""
        self.config_parser = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )

        if config_file is None:
            # Try config_local.ini first (gitignored), then config.ini
            config_files = [
                os.path.join(self._detected_project_root, "config_local.ini"),
                os.path.join(self._detected_project_root, "config.ini"),
            ]

            for config_file in config_files:
                if os.path.exists(config_file):
                    print(f"📋 Loading configuration from: {config_file}")
                    self.config_parser.read(config_file)
                    self._config_file_used = config_file
                    break
            else:
                raise FileNotFoundError(
                    f"No configuration file found. Expected one of: {config_files}\n"
                    f"Please create config_local.ini or ensure config.ini exists."
                )
        else:
            if not os.path.exists(config_file):
                raise FileNotFoundError(f"Configuration file not found: {config_file}")
            print(f"📋 Loading configuration from: {config_file}")
            self.config_parser.read(config_file)
            self._config_file_used = config_file

    def _expand_path(self, path_str):
        """Expand environment variables and resolve paths"""
        if path_str:
            return os.path.expandvars(os.path.expanduser(path_str))
        return path_str

    def _setup_paths(self):
        """Set up all derived paths from configuration"""

        # Read paths from configuration
        self._base_workspace = self._expand_path(self.config_parser.get("paths", "base_workspace"))
        self._cvmfs_eden_path = self._expand_path(self.config_parser.get("paths", "eden_path"))
        self._data_base_dir = self._expand_path(self.config_parser.get("paths", "data_base_dir"))

        # LE3 input data directories

        if self.config_parser.has_option("paths", "catred_dir"):
            self.catred_dir = self._expand_path(self.config_parser.get("paths", "catred_dir"))
        else:
            self.catred_dir = None

        if self.config_parser.has_option("paths", "effcovmask_dir"):
            self.effcovmask_dir = self._expand_path(
                self.config_parser.get("paths", "effcovmask_dir")
            )
        else:
            self.effcovmask_dir = None

        if self.config_parser.has_option("paths", "mosaic_dir"):
            self.mosaic_dir = self._expand_path(self.config_parser.get("paths", "mosaic_dir"))
        else:
            self.mosaic_dir = None

        # LE3 PFs working directories

        if self.config_parser.has_option("paths", "detintile_dir"):
            self.detintile_dir = self._expand_path(self.config_parser.get("paths", "detintile_dir"))
        else:
            self.detintile_dir = None

        if self.config_parser.has_option("paths", "mergedetcat_dir"):
            self.mergedetcat_dir = self._expand_path(
                self.config_parser.get("paths", "mergedetcat_dir")
            )
        else:
            self.mergedetcat_dir = None

        if self.config_parser.has_option("paths", "gluematchcat_dir"):
            self.gluematchcat_dir = self._expand_path(
                self.config_parser.get("paths", "gluematchcat_dir")
            )
        else:
            self.gluematchcat_dir = None

        if self.config_parser.has_option("paths", "characterization_dir"):
            self.characterization_dir = self._expand_path(
                self.config_parser.get("paths", "characterization_dir")
            )
        else:
            self.characterization_dir = None

        # Environment paths
        self.eden_path = self._cvmfs_eden_path

        # Project paths - use auto-detected git repository root
        self.project_root = self._detected_project_root

    def get_gluematchcat_clusters_xml(self):
        """Get path to GlueMatchCat clusters XML file"""
        if self.config_parser.has_option("files", "gluematchcat_clusters"):
            xmlname = self.config_parser.get("files", "gluematchcat_clusters")
            if not xmlname:
                return None
            expanded_path = self._expand_path(xmlname)
            if os.path.isabs(expanded_path):
                return expanded_path
            else:
                if self.gluematchcat_dir:
                    return os.path.join(self.gluematchcat_dir, xmlname)
                else:
                    return None
        else:
            return None

    def has_gluematchcat(self):
        """Check if gluematchcat file is available"""
        gluematchcat_xml = self.get_gluematchcat_clusters_xml()
        return gluematchcat_xml is not None and os.path.exists(gluematchcat_xml)

    def _parse_list_value(self, value: str) -> List[str]:
        """
        Parse a config value that might be a list in various formats.

        Supports:
        - Python list syntax: [item1, item2, item3]
        - Multi-line format with brackets
        - JSON file path

        Args:
            value: The config value string

        Returns:
            List of strings (file paths)
        """
        import ast

        value = value.strip()

        # Check if it's a list in Python syntax
        if value.startswith("[") and value.endswith("]"):
            try:
                # Try to parse as Python literal
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    # Expand paths and clean whitespace
                    return [self._expand_path(item.strip()) for item in parsed]
            except (ValueError, SyntaxError):
                try:
                    parsed = [i.strip("\n") for i in value.strip("[]").split(",")]
                    assert all(i.endswith(".xml") for i in parsed)
                    return [self._expand_path(item) for item in parsed]
                except Exception:
                    pass

        # Otherwise treat as single path (could be JSON file)
        return [self._expand_path(value)]

    def get_detintile_list_files(self, det_algorithm):
        """
        Get path to detection files list for selected algorithm
        args:
            algorithm (str): 'PZWAV' or 'AMICO' or 'BOTH'
        """
        detintile_key_map = {
            "pzwav": ["detintile_pzwav_list"],
            "amico": ["detintile_amico_list"],
            "both": ["detintile_pzwav_list", "detintile_amico_list"],
        }
        algorithm_lower = det_algorithm.lower()
        if algorithm_lower not in detintile_key_map:
            raise ValueError(f"Unknown algorithm: {det_algorithm}. Supported: PZWAV, AMICO, BOTH")

        filename_keys = detintile_key_map[algorithm_lower]
        # if not isinstance(filename_keys, list):
        #     filename_keys = [filename_keys]

        files_list_dict = {}
        for key in filename_keys:
            if self.config_parser.has_option("files", key):
                raw_value = self.config_parser.get("files", key)
                parsed_list = self._parse_list_value(raw_value)

                # If we got a list from config (not a JSON file path), create temp JSON file
                if len(parsed_list) > 1 or (
                    len(parsed_list) == 1 and not parsed_list[0].endswith(".json")
                ):
                    # Create a temporary JSON file with the list
                    import tempfile
                    import json

                    temp_dir = tempfile.gettempdir()
                    temp_file = os.path.join(temp_dir, f"{key}_temp.json")

                    with open(temp_file, "w") as f:
                        json.dump(parsed_list, f, indent=2)

                    files_list_dict[key] = temp_file
                    print(
                        f"Debug: Created temporary JSON file for {key}: {temp_file} with {len(parsed_list)} files"
                    )
                else:
                    # Single JSON file path - use directly
                    files_list_dict[key] = parsed_list[0]
                    print(f"Debug: Using JSON file for {key}: {parsed_list[0]}")
            else:
                print(f"Warning: No configuration found for {key} in [files] section")

        return files_list_dict

    def get_mergedetcat_xml_files(self, det_algorithm):
        """Get paths to mergedetcat XML files for both algorithms"""
        mergedetcat_key_map = {
            "pzwav": ["mergedetcat_pzwav"],
            "amico": ["mergedetcat_amico"],
            "both": ["mergedetcat_pzwav", "mergedetcat_amico"],
        }
        algorithm_lower = det_algorithm.lower()
        if algorithm_lower not in mergedetcat_key_map:
            raise ValueError(f"Unknown algorithm: {det_algorithm}. Supported: PZWAV, AMICO, BOTH")

        filename_keys = mergedetcat_key_map[algorithm_lower]
        # if not isinstance(filename_keys, list):
        #     filename_keys = [filename_keys]

        files = {}
        for key in filename_keys:
            if self.config_parser.has_option("files", key):
                filename = self.config_parser.get("files", key)
                expanded_path = self._expand_path(filename)
                if os.path.isabs(expanded_path):
                    files[key] = expanded_path
                else:
                    files[key] = os.path.join(self.mergedetcat_dir, filename)

        return files

    def get_characterization_xml_files(self, char_type, det_algorithm):
        pass

    def get_catred_fileinfo_csv(self):
        """Get path to catred file info CSV (hardcoded filename in catred_dir)"""
        filename = "catred_fileinfo.csv"
        return os.path.join(self.catred_dir, filename)

    def get_catred_dsr(self):
        """Get CATRED dataset release from configuration"""
        if self.config_parser.has_option("paths", "catred_ds_release"):
            dsr = self.config_parser.get("paths", "catred_ds_release")
            return dsr.strip("'\"")  # Remove quotes if present
        return None

    def get_catred_polygons_pkl(self):
        """Get path to catred polygons pickle file (hardcoded filename in catred_dir)"""
        filename = "catred_polygons_by_tileid.pkl"
        return os.path.join(self.catred_dir, filename)

    def get_effcovmask_fileinfo_csv(self):
        """Get path to effective coverage mask file info CSV (hardcoded filename in effcovmask_dir)"""
        filename = "effcovmask_fileinfo.csv"
        return os.path.join(self.effcovmask_dir, filename)

    def get_effcovmask_dsr(self):
        """Get effective coverage mask dataset release from configuration"""
        if self.config_parser.has_option("paths", "effcovmask_ds_release"):
            dsr = self.config_parser.get("paths", "effcovmask_ds_release")
            return dsr.strip("'\"")  # Remove quotes if present
        return None

    def get_corrected_mask_fits(self):
        """Get path to combined/corrected HEALPix mask FITS file.

        Returns None if not configured. When set, this mask is used as the
        default instead of per-tile effective coverage masks.
        """
        if self.config_parser.has_option("paths", "corrected_mask_fits"):
            path = self.config_parser.get("paths", "corrected_mask_fits")
            return path.strip()
        return None

    def _get_mosaic_option(self, option_name: str, fallback=None):
        """Get a value from [mosaic] section with optional fallback."""
        if self.config_parser.has_option("mosaic", option_name):
            return self.config_parser.get("mosaic", option_name)
        return fallback

    def get_mosaic_provider_default(self) -> str:
        """Get default mosaic provider."""
        provider = self._get_mosaic_option("provider_default", "local_fits")
        return str(provider).strip().lower()

    def get_esa_source_default(self) -> str:
        """Get default ESA/HiPS source identifier."""
        source_id = self._get_mosaic_option("esa_source_default", "CDS/P/DSS2/color")
        return str(source_id).strip()

    def get_esa_mocserver_url(self) -> str:
        """Get public source discovery endpoint for ESA/HiPS surveys."""
        return str(
            self._get_mosaic_option(
                "esa_mocserver_url",
                "https://alasky.cds.unistra.fr/MocServer/query?expr=dataproduct_type%3Dimage&fmt=json",
            )
        ).strip()

    def get_esa_cutout_base_url(self) -> str:
        """Get cutout endpoint for HiPS image extraction."""
        return str(
            self._get_mosaic_option(
                "esa_cutout_base_url", "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
            )
        ).strip()

    def get_esa_timeout_seconds(self) -> int:
        """Get network timeout for ESA source discovery and cutout requests."""
        raw_value = self._get_mosaic_option("esa_timeout_seconds", "30")
        try:
            return max(1, int(str(raw_value).strip()))
        except ValueError:
            return 30

    def get_esa_source_cache_ttl_seconds(self) -> int:
        """Get in-memory cache TTL for discovered public ESA sources."""
        raw_value = self._get_mosaic_option("esa_source_cache_ttl_seconds", "21600")
        try:
            return max(60, int(str(raw_value).strip()))
        except ValueError:
            return 21600

    def get_esa_cutout_width(self) -> int:
        """Get requested cutout width (pixels) for ESA cutouts."""
        raw_value = self._get_mosaic_option("esa_cutout_width", "768")
        try:
            return max(64, min(2048, int(str(raw_value).strip())))
        except ValueError:
            return 768

    def get_esa_cutout_height(self) -> int:
        """Get requested cutout height (pixels) for ESA cutouts."""
        raw_value = self._get_mosaic_option("esa_cutout_height", "768")
        try:
            return max(64, min(2048, int(str(raw_value).strip())))
        except ValueError:
            return 768

    def get_esa_cutout_format(self) -> str:
        """Get image format for ESA HiPS cutout requests.

        Returns 'fits' (default) for 32-bit float data with WCS-derived bounds,
        or 'jpg' for 8-bit JPEG with geometric bounds (faster, lower quality).
        """
        raw_value = str(self._get_mosaic_option("esa_cutout_format", "fits")).strip().lower()
        return "fits" if raw_value in {"fits", "fit"} else "jpg"

    def get_mosaic_select_best_local_file(self) -> bool:
        """Choose local mosaic file strategy: False uses first match for speed, True scores candidates."""
        raw_value = str(self._get_mosaic_option("select_best_local_file", "false")).strip().lower()
        return raw_value in {"1", "true", "yes", "on"}

    def validate_paths(self):
        """Validate that critical paths exist and return status"""
        issues = []

        # Check critical directories
        critical_dirs = [
            ("Base workspace", self._base_workspace),
            ("Base Data directory", self._data_base_dir),
        ]

        for name, path in critical_dirs:
            if not os.path.exists(path):
                issues.append(f"❌ {name}: {path} does not exist")
            else:
                print(f"✅ {name}: {path}")

        # Check optional directories
        optional_dirs = [
            ("CATRED directory", self.catred_dir),
            ("Effective coverage mask directory", self.effcovmask_dir),
            ("Mosaic directory", self.mosaic_dir),
            ("DetIntile directory", self.detintile_dir),
            ("MergeDetCat directory", self.mergedetcat_dir),
            ("GlueMatchCat directory", self.gluematchcat_dir),
            ("Characterization directory", self.characterization_dir),
        ]

        for name, path in optional_dirs:
            if not os.path.exists(path):
                print(f"⚠️  {name}: {path} does not exist (optional)")
            else:
                print(f"✅ {name}: {path}")

        # Check environment
        eden_active = self.eden_path in os.environ.get("PATH", "")
        if eden_active:
            print(f"✅ EDEN environment is active")
        else:
            print(f"⚠️  EDEN environment not detected in PATH")

        return len(issues) == 0, issues

    def print_config_summary(self):
        """Print a summary of current configuration"""
        print("=== Cluster Visualization Configuration ===")
        print(f"Configuration file: {self._config_file_used}")
        print(f"Base workspace: {self._base_workspace}")
        print(f"EDEN path: {self.eden_path}")
        print(f"Project root (auto-detected): {self.project_root}")
        print("")
        print("Data directories:")
        print(f"  CATRED directory: {self.catred_dir}")
        print(f"  Effective coverage mask directory: {self.effcovmask_dir}")
        print(f"  Mosaic directory: {self.mosaic_dir}")
        print("")
        print("Working directories:")
        print(f"  DetIntile directory: {self.detintile_dir}")
        print(f"  MergeDetCat directory: {self.mergedetcat_dir}")
        print(f"  GlueMatchCat directory: {self.gluematchcat_dir}")
        print(f"  Characterization directory: {self.characterization_dir}")
        print("===========================================")


# Global configuration instance (lazy initialization)
_config: Optional[Config] = None


def get_config(config_file=None):
    """Get the global configuration instance or create a new one with custom config file"""
    global _config

    if config_file:
        # Return a new instance with custom config file (don't update global)
        return Config(config_file)

    # Return or create the global instance
    if _config is None:
        _config = Config()
    return _config


# Create a property-like access for backward compatibility
# This will be evaluated lazily when first accessed
class _ConfigProxy:
    """Proxy object for lazy config initialization"""

    def __getattr__(self, name):
        return getattr(get_config(), name)

    def __dir__(self):
        return dir(get_config())


config = _ConfigProxy()


def validate_environment():
    """Validate the current environment and return status"""
    return get_config().validate_paths()


# Environment variables fallback
def from_env(var_name, default_value):
    """Get value from environment variable with fallback to default"""
    return os.environ.get(var_name, default_value)


# Alternative configuration for different environments
class ConfigFromEnv(Config):
    """Configuration class that reads from environment variables with INI fallback"""

    def __init__(self, config_file=None):
        super().__init__(config_file)

        # Override with environment variables if they exist
        env_workspace = os.environ.get("EUCLID_WORKSPACE")
        if env_workspace:
            self._base_workspace = env_workspace
            print(f"🌍 Using EUCLID_WORKSPACE from environment: {env_workspace}")

        env_eden = os.environ.get("EDEN_PATH")
        if env_eden:
            self._cvmfs_eden_path = env_eden
            self.eden_path = env_eden
            print(f"🌍 Using EDEN_PATH from environment: {env_eden}")

        # Re-setup paths with environment overrides
        self._setup_paths()


if __name__ == "__main__":
    # Test configuration when run directly
    config.print_config_summary()
    is_valid, issues = validate_environment()

    if not is_valid:
        print("\n❌ Configuration issues found:")
        for issue in issues:
            print(f"  {issue}")
        print("\nPlease update the paths in config.py to match your environment.")
    else:
        print("\n✅ Configuration is valid!")
