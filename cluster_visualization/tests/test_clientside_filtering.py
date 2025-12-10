#!/usr/bin/env python3
"""
Test script to verify client-side threshold filtering implementation
"""

import sys
import os

# Add the cluster_visualization directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cluster_visualization"))

try:
    from callbacks.main_plot import MainPlotCallbacks
    from src.data.catred_handler import CATREDHandler
    from src.visualization.traces import TraceCreator
    import inspect

    print("✓ All modules imported successfully")

    # Test 1: Check that MainPlotCallbacks has client-side callback method
    methods = [method for method in dir(MainPlotCallbacks) if not method.startswith("_")]
    if "_setup_threshold_clientside_callback" in dir(MainPlotCallbacks):
        print("✓ Client-side threshold callback method found")
    else:
        print("✗ Client-side threshold callback method NOT found")

    # Test 2: Check CATRED handler has new methods
    handler = CATREDHandler()

    if hasattr(handler, "get_radec_mertile_with_coverage"):
        print("✓ get_radec_mertile_with_coverage method found")
        # Check method signature
        sig = inspect.signature(handler.get_radec_mertile_with_coverage)
        params = list(sig.parameters.keys())
        expected_params = ["mertileid", "data"]
        if all(param in params for param in expected_params):
            print("  ✓ Method signature correct")
        else:
            print(f"  ✗ Method signature incorrect: {params}")
    else:
        print("✗ get_radec_mertile_with_coverage method NOT found")

    if hasattr(handler, "update_catred_data_with_coverage"):
        print("✓ update_catred_data_with_coverage method found")
    else:
        print("✗ update_catred_data_with_coverage method NOT found")

    # Test 3: Check that TraceCreator can handle effective coverage data
    trace_creator = TraceCreator()

    # Create mock data with effective coverage
    mock_catred_data = {
        "ra": [150.0, 151.0, 152.0],
        "dec": [2.0, 2.1, 2.2],
        "phz_mode_1": [0.5, 0.6, 0.7],
        "phz_70_int": [[0.1, 0.9], [0.2, 1.0], [0.3, 1.1]],
        "phz_pdf": [None, None, None],
        "effective_coverage": [0.9, 0.7, 0.85],
    }

    try:
        hover_text = trace_creator._format_catred_hover_text(mock_catred_data)
        if len(hover_text) == 3 and "Effective Coverage:" in hover_text[0]:
            print("✓ Hover text formatting includes effective coverage")
        else:
            print("✗ Hover text formatting missing effective coverage")
    except Exception as e:
        print(f"✗ Error testing hover text formatting: {e}")

    print("\n✅ Client-side filtering implementation verification completed!")

except Exception as e:
    print(f"✗ Error during testing: {e}")
    import traceback

    traceback.print_exc()
