"""
Comprehensive test runner for all cluster visualization modules.

Runs all tests and provides a summary of results for each module.
Handles missing modules gracefully and provides detailed reporting.
"""

import importlib
import os
import sys
import unittest
from io import StringIO

# Add the source directories to the path
# Add cluster_visualization root for package imports
cluster_viz_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, cluster_viz_root)

# Add cluster_visualization/src for direct imports
src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, src_dir)

# Add current directory for test imports
current_dir = os.path.dirname(__file__)
sys.path.insert(0, current_dir)


def check_module_availability():
    """Check which modules are available for testing"""
    available_modules = {}

    modules_to_check = [
        ("data.loader", "DataLoader"),
        ("data.catred_handler", "CATREDHandler"),
        ("visualization.traces", "TraceCreator"),
        ("visualization.figures", "FigureManager"),
        ("callbacks.main_plot", "MainPlotCallbacks"),
        ("callbacks.mer_callbacks", "MERCallbacks"),
        ("callbacks.ui_callbacks", "UICallbacks"),
        ("callbacks.phz_callbacks", "PHZCallbacks"),
        ("ui.layout", "AppLayout"),
        ("core.app", "ClusterVisualizationCore"),
    ]

    for module_name, class_name in modules_to_check:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            available_modules[module_name] = True
            print(f"✓ {module_name}.{class_name} - Available")
        except ImportError as e:
            available_modules[module_name] = False
            print(f"✗ {module_name}.{class_name} - Not available: {e}")

    return available_modules


def run_test_module(test_module_name, description):
    """Run a specific test module and return results"""
    print(f"\n{'='*60}")
    print(f"Running {description}")
    print(f"{'='*60}")

    try:
        # Import the test module from current directory
        test_module = importlib.import_module(test_module_name)

        # Create a test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_module)

        # Run the tests with a string buffer to capture output
        stream = StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)

        # Print results
        print(stream.getvalue())

        return {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "success": result.wasSuccessful(),
        }

    except ImportError as e:
        print(f"Could not import test module {test_module_name}: {e}")
        return {
            "tests_run": 0,
            "failures": 0,
            "errors": 1,
            "skipped": 0,
            "success": False,
            "import_error": str(e),
        }
    except Exception as e:
        print(f"Error running tests for {test_module_name}: {e}")
        return {
            "tests_run": 0,
            "failures": 0,
            "errors": 1,
            "skipped": 0,
            "success": False,
            "error": str(e),
        }


def main():
    """Main test runner function"""
    print("Cluster Visualization - Comprehensive Test Suite")
    print("=" * 60)

    # Check module availability
    print("Checking module availability...")
    available_modules = check_module_availability()

    # Define test modules to run
    test_modules = [
        ("test_data_loader", "Data Loader Tests"),
        ("test_mer_handler", "MER Handler Tests"),
        ("test_trace_creator", "Trace Creator Tests"),
        ("test_figure_manager", "Figure Manager Tests"),
        ("test_callbacks", "Callbacks Tests"),
        ("test_ui_core", "UI and Core Tests"),
    ]

    # Run all test modules
    all_results = {}
    total_stats = {
        "total_tests": 0,
        "total_failures": 0,
        "total_errors": 0,
        "total_skipped": 0,
        "modules_tested": 0,
        "modules_successful": 0,
    }

    for test_module_name, description in test_modules:
        results = run_test_module(test_module_name, description)
        all_results[test_module_name] = results

        # Update totals
        total_stats["total_tests"] += results["tests_run"]
        total_stats["total_failures"] += results["failures"]
        total_stats["total_errors"] += results["errors"]
        total_stats["total_skipped"] += results["skipped"]
        total_stats["modules_tested"] += 1

        if results["success"]:
            total_stats["modules_successful"] += 1

    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    print(f"Modules tested: {total_stats['modules_tested']}")
    print(f"Modules successful: {total_stats['modules_successful']}")
    print(f"Total tests run: {total_stats['total_tests']}")
    print(f"Total failures: {total_stats['total_failures']}")
    print(f"Total errors: {total_stats['total_errors']}")
    print(f"Total skipped: {total_stats['total_skipped']}")

    # Detailed results per module
    print(f"\nDetailed Results:")
    print("-" * 40)

    for test_module_name, description in test_modules:
        if test_module_name in all_results:
            results = all_results[test_module_name]
            status = "✓ PASS" if results["success"] else "✗ FAIL"

            if "import_error" in results:
                print(f"{status} {description}: Import Error")
            elif "error" in results:
                print(f"{status} {description}: Runtime Error")
            else:
                print(
                    f"{status} {description}: {results['tests_run']} tests, "
                    f"{results['failures']} failures, {results['errors']} errors, "
                    f"{results['skipped']} skipped"
                )

    # Overall success
    overall_success = total_stats["total_failures"] == 0 and total_stats["total_errors"] == 0

    print(f"\n{'='*60}")
    if overall_success:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
        print("Check the detailed output above for specific failures.")

    print(f"{'='*60}")

    # Return exit code
    return 0 if overall_success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
