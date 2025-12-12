"""
Test package for cluster visualization modules.

Contains comprehensive tests for all modular components including
data loading, visualization, callbacks, and UI components.
"""

# Test configuration
import os
import sys

# Add the source directory to the path for testing
source_dir = os.path.join(os.path.dirname(__file__), "..", "cluster_visualization")
if source_dir not in sys.path:
    sys.path.insert(0, source_dir)


# Test utilities
def create_test_data():
    """Create mock test data for testing purposes"""
    import numpy as np
    import pandas as pd

    # Create sample merged data
    merged_data = pd.DataFrame(
        {
            "RA": np.random.uniform(12.0, 14.0, 50),
            "DEC": np.random.uniform(-1.0, 1.0, 50),
            "SNR_CLUSTER": np.random.uniform(3.0, 15.0, 50),
            "Z_CL": np.random.uniform(0.2, 1.0, 50),
            "NOBJ": np.random.randint(5, 50, 50),
        }
    )

    # Create sample tile data
    tile_data = pd.DataFrame(
        {
            "RA": np.random.uniform(12.0, 14.0, 20),
            "DEC": np.random.uniform(-1.0, 1.0, 20),
            "SNR_CLUSTER": np.random.uniform(2.0, 10.0, 20),
            "Z_CL": np.random.uniform(0.1, 0.8, 20),
        }
    )

    return {"merged_data": merged_data, "tile_data": tile_data, "snr_min": 2.0, "snr_max": 15.0}


def create_test_config():
    """Create mock configuration for testing"""

    class MockConfig:
        def __init__(self):
            self.data_dir = "/tmp/test_data"
            self.utils_dir = "/tmp/test_utils"
            self.output_dir = "/tmp/test_output"

    return MockConfig()


__all__ = ["create_test_data", "create_test_config"]
