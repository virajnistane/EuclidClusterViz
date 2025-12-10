"""
Core application module for cluster visualization.

Contains the main application coordination logic, browser management,
and server startup functionality.
"""

import webbrowser
import threading
import time
import sys
import getpass
import socket
from datetime import datetime, timedelta


class ConnectionMonitor:
    """Monitor user connections to detect if anyone has connected to the app"""

    def __init__(self):
        self.connections = set()
        self.start_time = datetime.now()
        self.warning_sent = False
        self.monitoring_active = True

    def record_connection(self, user_agent=None, ip=None):
        """Record a new connection"""
        connection_id = f"{ip or 'unknown'}:{user_agent or 'unknown'}"
        is_first_connection = len(self.connections) == 0
        self.connections.add(connection_id)

        if is_first_connection:
            print(f"✓ User successfully connected at {datetime.now().strftime('%H:%M:%S')}")
            if ip == "127.0.0.1" or ip == "localhost":
                print("  ✓ SSH tunnel appears to be working correctly")
            print(f"  Browser: {user_agent or 'unknown'}")
            print(f"  Connection from: {ip or 'unknown'}")
            print("")

    def check_connections(self, warn_after_minutes=1):  # Back to 1 minute for production
        """Check if any connections have been made and warn if not"""
        if self.warning_sent or not self.monitoring_active:
            return

        elapsed = datetime.now() - self.start_time
        if elapsed > timedelta(minutes=warn_after_minutes) and not self.connections:
            self.warning_sent = True
            elapsed_seconds = elapsed.total_seconds()

            # Get the actual hostname
            try:
                hostname = socket.gethostbyaddr(socket.gethostname())[0]
            except:
                hostname = "remotehost"

            print("\n" + "=" * 70)
            print("⚠️  WARNING: No users have connected yet!")
            print(f"   App has been running for {elapsed_seconds/60:.1f} minutes")
            print("")
            print("🔗 REQUIRED: SSH Tunnel Setup")
            print("   This app runs on a remote server and requires SSH tunneling.")
            print("   ")
            print("   1. Open a NEW terminal on your LOCAL machine")
            print("   2. Run this command:")
            print(f"      ssh -L 8050:localhost:8050 {getpass.getuser()}@{hostname}")
            print("   3. Keep that SSH connection alive")
            print("   4. Open your browser to: http://localhost:8050")
            print("")
            print("=" * 70 + "\n")

    def start_monitoring(self, check_interval=10):  # Check every 10 seconds
        """Start background monitoring thread"""

        def monitor():
            while self.monitoring_active:
                self.check_connections()
                time.sleep(check_interval)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def stop_monitoring(self):
        """Stop the monitoring"""
        self.monitoring_active = False


class ClusterVisualizationCore:
    """Core application coordination and browser management"""

    def __init__(self, app):
        """
        Initialize core application.

        Args:
            app: Dash application instance
        """
        self.app = app
        self.connection_monitor = ConnectionMonitor()

        # Set up Flask middleware to track connections if not already set up
        if not hasattr(app.server, "_connection_tracking_setup"):

            @app.server.before_request
            def track_connections():
                from flask import request

                user_agent = request.headers.get("User-Agent", "")
                ip = request.environ.get("REMOTE_ADDR", "unknown")
                # Only track browser connections (not internal Dash requests)
                if (
                    "Mozilla" in user_agent
                    or "Chrome" in user_agent
                    or "Safari" in user_agent
                    or "Firefox" in user_agent
                ):
                    self.connection_monitor.record_connection(user_agent, ip)

            app.server._connection_tracking_setup = True

    def open_browser(self, port=8050, delay=1.5):
        """Open browser after a short delay"""

        def open_browser_delayed():
            time.sleep(delay)
            webbrowser.open(f"http://localhost:{port}")

        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    def run(self, host="localhost", port=8050, debug=False, auto_open=True, external_access=False):
        """Run the Dash app"""
        # If external_access is True, bind to all interfaces and don't auto-open browser
        if external_access:
            host = "0.0.0.0"
            auto_open = False

        if auto_open:
            self.open_browser(port)

        # Get the actual hostname for SSH instructions
        try:
            hostname = socket.gethostbyaddr(socket.gethostname())[0]
        except:
            hostname = "remotehost"

        print("=== Cluster Visualization Dash App ===")
        print(f"Server starting on: http://localhost:{port}")
        print("")
        print("📌 REMOTE ACCESS:")
        print(f"   If accessing remotely, ensure your SSH tunnel is active:")
        print(f"   ssh -L {port}:localhost:{port} {getpass.getuser()}@{hostname}")
        print(f"   Then open: http://localhost:{port}")
        print("")
        print("Loading data and setting up visualization...")
        print("Press Ctrl+C to stop the server")
        print("")

        # Start connection monitoring
        if hasattr(self, "connection_monitor"):
            self.connection_monitor.start_monitoring()
            print("Connection monitoring started - will warn if no users connect within 1 minute")
            print("")

        try:
            self.app.run_server(
                host=host,
                port=port,
                debug=debug,
                dev_tools_hot_reload=False,
                dev_tools_ui=False,
                dev_tools_props_check=False,
            )
        finally:
            # Stop monitoring when server shuts down
            if hasattr(self, "connection_monitor"):
                self.connection_monitor.stop_monitoring()

    def try_multiple_ports(self, ports=[8050, 8051, 8052], **kwargs):
        """Try to run on multiple ports if default is busy"""
        for port in ports:
            try:
                self.run(port=port, **kwargs)
                break
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"Port {port} is busy, trying next port...")
                    continue
                else:
                    raise e

    @staticmethod
    def check_command_line_args():
        """Check command line arguments for external access"""
        return "--external" in sys.argv or "--remote" in sys.argv
