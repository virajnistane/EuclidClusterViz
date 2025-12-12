#!/usr/bin/env python3
"""
Simple test script for the Dash app
Tests if the app can be imported and initialized without errors
"""

import os
import sys

# Add the current directory to path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_dash_app_import():
    """Test if the Dash app can be imported and initialized"""
    try:
        print("Testing Dash app import...")

        # Set environment variable to avoid browser opening during test
        os.environ["DASH_TEST_MODE"] = "1"

        from cluster_dash_app import ClusterVisualizationApp

        print("✓ Dash app imported successfully")

        # Try to initialize the app
        app = ClusterVisualizationApp()
        print("✓ Dash app initialized successfully")

        # Check if the app has the required components
        assert hasattr(app, "app"), "App should have a dash app instance"
        assert hasattr(app, "data_cache"), "App should have data cache"
        assert hasattr(app, "load_data"), "App should have load_data method"
        assert hasattr(app, "create_traces"), "App should have create_traces method"
        print("✓ All required methods and attributes present")

        print("\n🎉 Dash app test passed! The app is ready to run.")
        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("   Make sure all required packages are installed in your environment")
        return False
    except Exception as e:
        print(f"✗ Initialization error: {e}")
        return False


if __name__ == "__main__":
    success = test_dash_app_import()
    sys.exit(0 if success else 1)
