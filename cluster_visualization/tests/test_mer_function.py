#!/usr/bin/env python3
"""
Quick test to verify the get_radec_mertile function returns the correct dictionary format
"""

import os
import sys

sys.path.append("/pbs/home/v/vnistane/ClusterVisualization/cluster_visualization/src")


# Mock the required modules for testing
class MockFits:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __getitem__(self, index):
        # Mock data structure with the required columns
        class MockData:
            def __init__(self):
                self.data = {
                    "RIGHT_ASCENSION": [150.0, 151.0, 152.0],
                    "DECLINATION": [2.0, 2.1, 2.2],
                    "PHZ_MODE_1": [0.5, 0.6, 0.7],
                    "PHZ_70_INT": [0.45, 0.55, 0.65],
                    "PHZ_PDF": [0.8, 0.9, 1.0],
                }
                self.columns = MockColumns()

            def __getitem__(self, key):
                class MockColumn:
                    def __init__(self, data):
                        self._data = data

                    def tolist(self):
                        return self._data

                return MockColumn(self.data[key])

        class MockColumns:
            def __init__(self):
                self.names = [
                    "RIGHT_ASCENSION",
                    "DECLINATION",
                    "PHZ_MODE_1",
                    "PHZ_70_INT",
                    "PHZ_PDF",
                ]

        return MockData()


# Mock the fits module
import types

fits_mock = types.ModuleType("fits")
fits_mock.open = MockFits # type: ignore

# Mock other required modules
import pandas as pd
from shapely.geometry import Polygon


# Create a simple test
def test_get_radec_mertile():
    # Import after mocking
    sys.modules["astropy.io.fits"] = fits_mock
    from cluster_dash_app import ClusterDashApp # type: ignore

    app = ClusterDashApp()

    # Create mock data
    mock_catred_info = pd.DataFrame(
        {
            "fits_file": ["/fake/path/file1.fits"],
            "polygon": [Polygon([(150, 2), (151, 2), (151, 3), (150, 3)])],
        },
        index=[1001],
    )

    mock_data = {"catred_info": mock_catred_info}

    # Test the function
    result = app.get_radec_mertile(1001, mock_data)

    print("Function returned:", result)
    print("Type:", type(result))

    # Verify it's a dictionary with the expected keys
    expected_keys = ["RIGHT_ASCENSION", "DECLINATION", "PHZ_MODE_1", "PHZ_70_INT", "PHZ_PDF"]
    if isinstance(result, dict):
        print("✓ Returns dictionary")
        for key in expected_keys:
            if key in result:
                print(f"✓ Has {key}: {len(result[key])} items")
            else:
                print(f"✗ Missing {key}")
    else:
        print("✗ Does not return dictionary")

    return result


if __name__ == "__main__":
    # Mock os.path.exists to return True for our test
    original_exists = os.path.exists
    os.path.exists = lambda path: True

    try:
        result = test_get_radec_mertile()
        print("\nTest completed successfully!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Restore original function
        os.path.exists = original_exists
