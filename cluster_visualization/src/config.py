#!/usr/bin/env python3
"""
Configuration file for Cluster Visualization tools

This file contains all user-specific paths and settings that need to be
configured for different users or environments.

The configuration is read from config.ini (or config_local.ini if it exists).
"""

import os
import subprocess
import configparser
from pathlib import Path

def get_git_repo_root():
    """Get the root directory of the current git repository"""
    try:
        # Try to get the git repository root
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
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
                os.path.join(self._detected_project_root, 'config_local.ini'),
                os.path.join(self._detected_project_root, 'config.ini')
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
        self._base_workspace = self._expand_path(self.config_parser.get('paths', 'base_workspace'))
        self._cvmfs_eden_path = self._expand_path(self.config_parser.get('paths', 'eden_path'))
        
        # Main data directories
        self.mergedetcat_dir = self._expand_path(self.config_parser.get('paths', 'mergedetcat_dir'))
        self.mergedetcat_data_dir = os.path.join(self.mergedetcat_dir, 'data')
        self.mergedetcat_inputs_dir = os.path.join(self.mergedetcat_dir, 'inputs')
        
        # Downloads directory
        self.rr2_downloads_dir = self._expand_path(self.config_parser.get('paths', 'rr2_downloads_dir'))
        
        # Catalog and mask directories (check paths section first, then files section for backward compatibility)
        if self.config_parser.has_option('paths', 'catred_dir'):
            self.catred_dir = self._expand_path(self.config_parser.get('paths', 'catred_dir'))
        else:
            self.catred_dir = os.path.join(self.rr2_downloads_dir, 'DpdLE3clFullInputCat')
            
        if self.config_parser.has_option('paths', 'effcov_mask_dir'):
            self.effcov_mask_dir = self._expand_path(self.config_parser.get('paths', 'effcov_mask_dir'))
        else:
            self.effcov_mask_dir = os.path.join(self.rr2_downloads_dir, 'DpdHealpixEffectiveCoverageVMPZ')
        
        if self.config_parser.has_option('paths', 'mosaic_dir'):
            self.mosaic_dir = self._expand_path(self.config_parser.get('paths', 'mosaic_dir'))
        else:
            self.mosaic_dir = os.path.join(self.rr2_downloads_dir, 'DpdMerBksMosaic')

        # Environment paths
        self.eden_path = self._cvmfs_eden_path
        
        # Project paths - use auto-detected git repository root
        self.project_root = self._detected_project_root
    
    def get_mergedetcat_xml(self, algorithm):
        """Get algorithm-specific output directory"""
        algorithm_lower = algorithm.lower()
        if algorithm_lower == 'pzwav':
            xmlname = self.config_parser.get('files', 'pzwav_merged_xml')
        elif algorithm_lower == 'amico':
            xmlname = self.config_parser.get('files', 'amico_merged_xml')
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}. Supported: PZWAV, AMICO")
        
        # Check if it's an absolute path
        expanded_path = self._expand_path(xmlname)
        if os.path.isabs(expanded_path):
            return expanded_path
        else:
            return os.path.join(self.mergedetcat_dir, xmlname)

    def get_detfiles_list(self, algorithm):
        """Get path to detection files list for given algorithm"""
        algorithm_lower = algorithm.lower()
        if algorithm_lower == 'pzwav':
            filename = self.config_parser.get('files', 'pzwav_detfiles_list')
        elif algorithm_lower == 'amico':
            filename = self.config_parser.get('files', 'amico_detfiles_list')
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}. Supported: PZWAV, AMICO")
        
        # Check if it's an absolute path
        expanded_path = self._expand_path(filename)
        if os.path.isabs(expanded_path):
            return expanded_path
        else:
            return os.path.join(self.mergedetcat_dir, filename)
    
    def get_catred_fileinfo_csv(self):
        """Get path to catred file info CSV (hardcoded filename in catred_dir)"""
        filename = 'catred_fileinfo.csv'
        return os.path.join(self.catred_dir, filename)
    
    def get_catred_polygons_pkl(self):
        """Get path to catred polygons pickle file (hardcoded filename in catred_dir)"""
        filename = 'catred_polygons_by_tileid.pkl'
        return os.path.join(self.catred_dir, filename)
    
    def get_effcovmask_fileinfo_csv(self):
        """Get path to effective coverage mask file info CSV (hardcoded filename in effcov_mask_dir)"""
        filename = 'effcovmask_fileinfo.csv'
        return os.path.join(self.effcov_mask_dir, filename)
    
    def validate_paths(self):
        """Validate that critical paths exist and return status"""
        issues = []
        
        # Check critical directories
        critical_dirs = [
            ('Base workspace', self._base_workspace),
            ('MergeDetCat directory', self.mergedetcat_dir),
            ('Data directory', self.mergedetcat_data_dir),
            ('Inputs directory', self.mergedetcat_inputs_dir),
            ('RR2 downloads directory', self.rr2_downloads_dir)
        ]
        
        for name, path in critical_dirs:
            if not os.path.exists(path):
                issues.append(f"❌ {name}: {path} does not exist")
            else:
                print(f"✅ {name}: {path}")
        
        # Check optional directories
        optional_dirs = [
            ('CATRED directory', self.catred_dir),
            ('Effective coverage mask directory', self.effcov_mask_dir),
            ('EDEN environment', self.eden_path)
        ]
        
        for name, path in optional_dirs:
            if not os.path.exists(path):
                print(f"⚠️  {name}: {path} does not exist (optional)")
            else:
                print(f"✅ {name}: {path}")
        
        # Check environment
        eden_active = self.eden_path in os.environ.get('PATH', '')
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
        print(f"  MergeDetCat: {self.mergedetcat_dir}")
        print(f"  RR2 downloads: {self.rr2_downloads_dir}")
        print(f"  CATRED: {self.catred_dir}")
        print("")

# Global configuration instance
config = Config()

def get_config():
    """Get the global configuration instance"""
    return config

def validate_environment():
    """Validate the current environment and return status"""
    return config.validate_paths()

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
        env_workspace = os.environ.get('EUCLID_WORKSPACE')
        if env_workspace:
            self._base_workspace = env_workspace
            print(f"🌍 Using EUCLID_WORKSPACE from environment: {env_workspace}")
        
        env_eden = os.environ.get('EDEN_PATH')  
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
