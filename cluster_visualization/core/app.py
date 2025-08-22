"""
Core application module for cluster visualization.

Contains the main application coordination logic, browser management,
and server startup functionality.
"""

import webbrowser
import threading
import time
import sys


class ClusterVisualizationCore:
    """Core application coordination and browser management"""
    
    def __init__(self, app):
        """
        Initialize core application.
        
        Args:
            app: Dash application instance
        """
        self.app = app
    
    def open_browser(self, port=8050, delay=1.5):
        """Open browser after a short delay"""
        def open_browser_delayed():
            time.sleep(delay)
            webbrowser.open(f'http://localhost:{port}')
        
        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    def run(self, host='localhost', port=8050, debug=False, auto_open=True, external_access=False):
        """Run the Dash app"""
        # If external_access is True, bind to all interfaces and don't auto-open browser
        if external_access:
            host = '0.0.0.0'
            auto_open = False
        
        if auto_open:
            self.open_browser(port)
        
        print("=== Cluster Visualization Dash App ===")
        if external_access:
            print(f"Starting server for external access on port {port}")
            print("Access from your local machine using:")
            print(f"  - SSH tunnel: ssh -L {port}:localhost:{port} username@this-server")
            print(f"  - Then open: http://localhost:{port} in your local browser")
            print("NOTE: Keep the SSH connection alive while using the app")
        else:
            print(f"Starting server at: http://{host}:{port}")
        print("Loading data and setting up visualization...")
        print("Press Ctrl+C to stop the server")
        print("")
        
        self.app.run_server(
            host=host,
            port=port,
            debug=debug,
            dev_tools_hot_reload=False,
            dev_tools_ui=False,
            dev_tools_props_check=False
        )
    
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
        return '--external' in sys.argv or '--remote' in sys.argv
