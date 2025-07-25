#!/usr/bin/env python3
"""
Configuration file for Cluster Visualization tools

This file contains all user-specific paths and settings that need to be
configured for different users or environments.
"""

import os
from pathlib import Path

class Config:
    """Configuration class for cluster visualization paths and settings"""
    
    def __init__(self):
        # Base configuration - modify these paths for your environment
        self._base_workspace = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir'
        self._cvmfs_eden_path = '/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1'
        self._user_home = '/pbs/home/v/vnistane'
        
        # Validate and set up paths
        self._setup_paths()
    
    def _setup_paths(self):
        """Set up all derived paths and validate they exist"""
        
        # Main data directories
        self.mergedetcat_dir = os.path.join(self._base_workspace, 'MergeDetCat/RR2_south')
        self.mergedetcat_data_dir = os.path.join(self.mergedetcat_dir, 'data')
        self.mergedetcat_inputs_dir = os.path.join(self.mergedetcat_dir, 'inputs')
        
        # Downloads and catalog directories
        self.rr2_downloads_dir = os.path.join(self._base_workspace, 'RR2_downloads')
        self.catred_dir = os.path.join(self.rr2_downloads_dir, 'DpdLE3clFullInputCat')
        self.effcov_mask_dir = os.path.join(self.rr2_downloads_dir, 'DpdHealpixEffectiveCoverageVMPZ')
        
        # Environment paths
        self.eden_path = self._cvmfs_eden_path
        
        # Project paths
        self.project_root = os.path.join(self._user_home, 'ClusterVisualization')
        self.utils_dir = os.path.join(self.project_root, 'cluster_visualization', 'utils')
    
    def get_output_dir(self, algorithm):
        """Get algorithm-specific output directory"""
        return os.path.join(self.mergedetcat_dir, f'outvn_mergedetcat_rr2south_{algorithm}_3')
    
    def get_detfiles_list(self, algorithm):
        """Get path to detection files list for given algorithm"""
        return os.path.join(self.mergedetcat_dir, f'detfiles_input_{algorithm.lower()}_3.json')
    
    def get_catred_fileinfo_csv(self):
        """Get path to catred file info CSV"""
        return os.path.join(self.rr2_downloads_dir, 'catred_fileinfo.csv')
    
    def get_catred_polygons_pkl(self):
        """Get path to catred polygons pickle file"""
        return os.path.join(self.rr2_downloads_dir, 'catred_polygons_by_tileid.pkl')
    
    def validate_paths(self):
        """Validate that critical paths exist and return status"""
        issues = []
        
        # Check critical directories
        critical_dirs = [
            ('Base workspace', self._base_workspace),
            ('MergeDetCat directory', self.mergedetcat_dir),
            ('Data directory', self.mergedetcat_data_dir),
            ('Inputs directory', self.mergedetcat_inputs_dir),
            ('RR2 downloads directory', self.rr2_downloads_dir),
            ('Utils directory', self.utils_dir)
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
        print(f"Base workspace: {self._base_workspace}")
        print(f"User home: {self._user_home}")
        print(f"EDEN path: {self.eden_path}")
        print(f"Project root: {self.project_root}")
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

def setup_environment_paths():
    """Add necessary paths to Python path"""
    import sys
    if config.utils_dir not in sys.path:
        sys.path.append(config.utils_dir)
        print(f"Added to Python path: {config.utils_dir}")

# Environment variables fallback
def from_env(var_name, default_value):
    """Get value from environment variable with fallback to default"""
    return os.environ.get(var_name, default_value)

# Alternative configuration for different environments
class ConfigFromEnv(Config):
    """Configuration class that reads from environment variables"""
    
    def __init__(self):
        # Read from environment with fallbacks
        self._base_workspace = from_env('EUCLID_WORKSPACE', '/sps/euclid/OU-LE3/CL/ial_workspace/workdir')
        self._cvmfs_eden_path = from_env('EDEN_PATH', '/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1')
        self._user_home = from_env('USER_HOME', os.path.expanduser('~'))
        
        super()._setup_paths()

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
