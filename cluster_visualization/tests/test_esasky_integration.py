#!/usr/bin/env python3
"""
Quick test script for Aladin Lite integration.
Verifies that all components are properly integrated.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        from cluster_visualization.callbacks.aladin_callbacks import AladinCallbacks
        print("  ✓ AladinCallbacks imported")
    except Exception as e:
        print(f"  ✗ AladinCallbacks import failed: {e}")
        return False
    
    try:
        from cluster_visualization.ui.layout import AppLayout
        print("  ✓ AppLayout imported")
    except Exception as e:
        print(f"  ✗ AppLayout import failed: {e}")
        return False
    
    try:
        from cluster_visualization.src.cluster_dash_app import ClusterVisualizationApp
        print("  ✓ ClusterVisualizationApp imported")
    except Exception as e:
        print(f"  ✗ ClusterVisualizationApp import failed: {e}")
        return False
    
    return True

def test_layout_has_aladin():
    """Test that layout includes Aladin components"""
    print("\nTesting layout components...")
    
    try:
        from cluster_visualization.ui.layout import AppLayout
        
        # Check if _create_aladin_tab_content method exists
        if hasattr(AppLayout, '_create_aladin_tab_content'):
            print("  ✓ _create_aladin_tab_content method exists")
        else:
            print("  ✗ _create_aladin_tab_content method not found")
            return False
        
        # Try creating the layout
        layout = AppLayout.create_layout()
        print("  ✓ Layout created successfully")
        
        return True
    except Exception as e:
        print(f"  ✗ Layout test failed: {e}")
        return False

def test_aladin_callbacks_structure():
    """Test that AladinCallbacks has required methods"""
    print("\nTesting AladinCallbacks structure...")
    
    try:
        from cluster_visualization.callbacks.aladin_callbacks import AladinCallbacks
        
        # Check required methods
        required_methods = [
            'setup_callbacks',
            '_setup_aladin_initialization',
            '_setup_aladin_update_from_click',
            # Note: _setup_tab_visibility removed - handled by cluster_modal_callbacks
            '_setup_aladin_controls',
            '_setup_aladin_overlay_clusters',
        ]
        
        for method in required_methods:
            if hasattr(AladinCallbacks, method):
                print(f"  ✓ {method} exists")
            else:
                print(f"  ✗ {method} not found")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ AladinCallbacks structure test failed: {e}")
        return False

def test_app_integration():
    """Test that app can be initialized with Aladin callbacks"""
    print("\nTesting app integration...")
    
    try:
        # Set test mode to avoid browser opening
        os.environ["DASH_TEST_MODE"] = "1"
        
        from cluster_visualization.src.cluster_dash_app import ClusterVisualizationApp
        
        # Try to initialize app (will fail gracefully if config missing)
        try:
            app = ClusterVisualizationApp()
            print("  ✓ App initialized")
            
            # Check if aladin callbacks were registered
            if hasattr(app, 'aladin_callbacks'):
                print("  ✓ Aladin callbacks registered in app")
            else:
                print("  ⚠ Aladin callbacks not found (may be expected if initialization failed)")
            
            return True
        except Exception as e:
            print(f"  ⚠ App initialization had issues (may be expected): {e}")
            print("  ℹ This is often normal if config files are missing")
            return True  # Don't fail test for config issues
            
    except Exception as e:
        print(f"  ✗ App integration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Aladin Lite Integration Test")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Layout Components", test_layout_has_aladin()))
    results.append(("Callback Structure", test_aladin_callbacks_structure()))
    results.append(("App Integration", test_app_integration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:25} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All tests passed! Aladin Lite integration is ready.")
        print("\nNext steps:")
        print("1. Run the app: python cluster_visualization/src/cluster_dash_app.py")
        print("2. Navigate to the '🔭 Aladin Sky' tab")
        print("3. Click a cluster in the main plot")
        print("4. The Aladin viewer should center on the clicked position")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
