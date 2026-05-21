"""
Core application module for cluster visualization.

Contains the main application coordination logic, browser management,
and server startup functionality.
"""

import getpass
import logging
import socket
import sys
import threading
import time
import webbrowser
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

    def check_connections(self, warn_after_minutes=1, bound_port=None):
        """Check if any connections have been made and warn if not"""
        if self.warning_sent or not self.monitoring_active:
            return

        elapsed = datetime.now() - self.start_time
        if elapsed > timedelta(minutes=warn_after_minutes) and not self.connections:
            self.warning_sent = True
            elapsed_seconds = elapsed.total_seconds()

            try:
                hostname = socket.gethostbyaddr(socket.gethostname())[0]
            except:
                hostname = "remotehost"

            remote_port = bound_port or 8050
            user = getpass.getuser()

            print("\n" + "=" * 70)
            print("⚠️  WARNING: No users have connected yet!")
            print(f"   App has been running for {elapsed_seconds/60:.1f} minutes")
            print("")
            print("🔗 REQUIRED: SSH Tunnel Setup")
            print("   This app runs on a remote server and requires SSH tunneling.")
            print("")
            print("   1. Open a NEW terminal on your LOCAL machine")
            print("   2. Run this command:")
            print(f"      ssh -L 8050:localhost:{remote_port} {user}@{hostname}")
            print("   3. Keep that SSH connection alive")
            print("   4. Open your browser to: http://localhost:8050")
            print("")
            print("   Then open a NEW terminal and run the tunnel command above.")
            print("=" * 70 + "\n")

    def start_monitoring(self, check_interval=10, bound_port=None):
        """Start background monitoring thread"""
        self._bound_port = bound_port

        def monitor():
            while self.monitoring_active:
                self.check_connections(bound_port=self._bound_port)
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

        import os as _os
        project_root = (
            _os.path.dirname(
                _os.path.dirname(
                    _os.path.dirname(
                        _os.path.abspath(__file__)))))
        
        user = getpass.getuser()
        print("=== Cluster Visualization Dash App ===")
        print(f"Server starting on port {port}")
        print("")
        print("┌─────────────────────────────────────────────────────────────┐")
        print("│  🖥️  REMOTE ACCESS — run this on your LOCAL machine:         │")
        print("│                                                             │")
        print(f"│ 1) ssh -L 8050:localhost:{port} {user}@{hostname}")
        print(f"│ 2) cd {project_root}")
        print("│ 3) ./launch.sh                                              │")
        print("│ 4) Then open in browser:  http://localhost:8050             │")
        print("│                                                             │")
        print("│  Run step 1 in a NEW terminal — keep the connection open.   │")
        print("└─────────────────────────────────────────────────────────────┘")
        print("")
        print("Loading data and setting up visualization...")
        print("Press Ctrl+C to stop the server")
        print("")
        # Suppress Dash/Flask/werkzeug startup banners — they show the remote port
        # which confuses users who should use localhost:8050 via the SSH tunnel.
        logging.getLogger("dash").setLevel(logging.WARNING)
        logging.getLogger("dash.dash").setLevel(logging.WARNING)
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        # Flask CLI banner uses click.echo(), not logging — patch it out directly.
        try:
            import flask.cli as _flask_cli
            _flask_cli.show_server_banner = lambda *a, **kw: None
        except Exception:
            pass

        # Start connection monitoring
        if hasattr(self, "connection_monitor"):
            self.connection_monitor.start_monitoring(bound_port=port)
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

    @staticmethod
    def _free_port_if_stale(port):
        """Kill any process owned by the current user that is listening on port."""
        import os as _os
        import signal
        import subprocess
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
                capture_output=True, text=True
            )
            pids = [int(p) for p in result.stdout.split() if p.strip()]
            uid = _os.getuid()
            for pid in pids:
                try:
                    proc_uid = _os.stat(f"/proc/{pid}").st_uid
                except OSError:
                    # /proc not available (non-Linux); fall back to checking via ps
                    try:
                        ps = subprocess.run(
                            ["ps", "-o", "uid=", "-p", str(pid)],
                            capture_output=True, text=True
                        )
                        proc_uid = int(ps.stdout.strip())
                    except Exception:
                        continue
                if proc_uid == uid:
                    _os.kill(pid, signal.SIGTERM)
                    print(f"  Freed port {port} (terminated stale PID {pid})")
        except Exception:
            pass  # lsof unavailable — fall through to normal port-busy error

    def try_multiple_ports(self, ports=[8050, 8051, 8052], **kwargs):
        """Try to run on multiple ports if default is busy"""
        for port in ports:
            self._free_port_if_stale(port)
            time.sleep(0.5)  # allow socket to leave TIME_WAIT after SIGTERM
            try:
                self.run(port=port, **kwargs)
                break
            except SystemExit:
                # werkzeug prints the error and calls sys.exit(1) on EADDRINUSE
                print(f"Port {port} is busy, trying next port...")
                continue
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
