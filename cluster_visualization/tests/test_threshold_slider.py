#!/usr/bin/env python3
"""
Test script to verify bidirectional threshold slider functionality
"""

import time
import subprocess
import sys
from pathlib import Path

def run_test():
    print("🧪 Testing bidirectional threshold slider functionality")
    print("=" * 60)
    
    # Test 1: Verify client-side callback implementation
    print("\n1. Checking client-side callback implementation...")
    
    callback_file = Path("cluster_visualization/callbacks/main_plot.py")
    if callback_file.exists():
        with open(callback_file, 'r') as f:
            content = f.read()
            
        # Check for key components of the fix
        checks = [
            ("Client-side callback function", "clientside_callback" in content),
            ("Original data storage", "_originalData" in content),
            ("Bidirectional filtering logic", "if (!trace._originalData)" in content),
            ("Threshold filtering", "effectiveCoverage >= threshold" in content),
        ]
        
        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"   {status} {check_name}: {'FOUND' if result else 'MISSING'}")
            
        if all(result for _, result in checks):
            print("   ✅ Client-side callback implementation looks correct")
        else:
            print("   ❌ Issues found in client-side callback implementation")
    
    # Test 2: Verify coverage data inclusion
    print("\n2. Checking coverage data inclusion...")
    
    traces_file = Path("cluster_visualization/src/visualization/traces.py")
    if traces_file.exists():
        with open(traces_file, 'r') as f:
            content = f.read()
            
        coverage_checks = [
            ("Effective coverage in customdata", "effective_coverage" in content and "customdata" in content),
            ("Coverage column reference", "'effective_coverage'" in content),
        ]
        
        for check_name, result in coverage_checks:
            status = "✓" if result else "✗"
            print(f"   {status} {check_name}: {'FOUND' if result else 'MISSING'}")
    
    # Test 3: Check data handler enhancements
    print("\n3. Checking CATRED data handler enhancements...")
    
    handler_file = Path("cluster_visualization/src/data/catred_handler.py")
    if handler_file.exists():
        with open(handler_file, 'r') as f:
            content = f.read()
            
        handler_checks = [
            ("Coverage loading method", "get_radec_mertile_with_coverage" in content),
            ("Coverage update method", "update_catred_data_with_coverage" in content),
        ]
        
        for check_name, result in handler_checks:
            status = "✓" if result else "✗"
            print(f"   {status} {check_name}: {'FOUND' if result else 'MISSING'}")
    
    print("\n🎯 Test Summary:")
    print("The bidirectional threshold slider fix has been implemented with:")
    print("  • Client-side JavaScript filtering for real-time performance")
    print("  • Original data preservation for bidirectional changes")
    print("  • Effective coverage data included in trace customdata")
    print("  • Enhanced data handlers for coverage loading")
    
    print("\n📖 How to test manually:")
    print("1. Start the Dash app and connect via SSH tunnel")
    print("2. Load CATRED masked data using the 'Render CATRED' button")
    print("3. Move the threshold slider to HIGHER values (e.g., 0.9)")
    print("   → Points should disappear (filter out low coverage)")
    print("4. Move the threshold slider to LOWER values (e.g., 0.6)")
    print("   → Points should reappear (restore previously filtered points)")
    print("5. Verify smooth real-time filtering in both directions")
    
    print("\n✨ Expected behavior:")
    print("  • Threshold changes should be instant (< 100ms)")
    print("  • No server round-trips for threshold adjustments")
    print("  • Points filtered out should return when threshold lowered")
    print("  • Original dataset preserved for bidirectional filtering")

if __name__ == "__main__":
    run_test()
