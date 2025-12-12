#!/usr/bin/env python3
"""
Test script to demonstrate connection monitoring functionality.
This will start the app and show the warning if no connections are made.
"""

import os
import signal
import sys
import threading
import time

# Add the project path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cluster_visualization", "src"))


def test_connection_monitoring():
    """Test the connection monitoring warning system"""
    print("=== Connection Monitoring Test ===")
    print("This test will start the Dash app without opening a browser")
    print("and demonstrate the warning system when no users connect.")
    print("")

    # Import after setting up path
    from cluster_visualization.src.cluster_dash_app import \
        ClusterVisualizationApp

    app = ClusterVisualizationApp()

    # Set up signal handler to stop cleanly
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print("\nStopping test...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    # Start the app in a separate thread
    def run_app():
        try:
            app.run(auto_open=False, debug=False)
        except:
            pass  # Ignore errors when stopping

    app_thread = threading.Thread(target=run_app, daemon=True)
    app_thread.start()

    print("App started. Waiting for connection warning...")
    print("The warning should appear in about 30 seconds if no one connects.")
    print("Press Ctrl+C to stop the test.")
    print("")

    # Wait for the test to finish or be interrupted
    try:
        # Wait for 60 seconds or until interrupted
        stop_event.wait(60)
    except KeyboardInterrupt:
        pass

    print("\nTest completed.")
    print("If you saw a warning message, the connection monitoring is working correctly!")


if __name__ == "__main__":
    test_connection_monitoring()
