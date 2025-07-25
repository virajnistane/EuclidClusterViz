#!/usr/bin/env python3
"""
Simple HTTP Server for Cluster Visualization
Serves the generated HTML file without complex dependencies
"""

import os
import sys
import http.server
import socketserver
import webbrowser
from pathlib import Path

def serve_visualization(port=8000, auto_open=True):
    """Serve the cluster visualization HTML file"""
    
    # Check for available HTML files
    html_files = []
    
    # Define search paths (relative to project root, not src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    current_output = os.path.join(project_dir, 'output', 'current')
    archive_output = os.path.join(project_dir, 'output', 'archive')
    
    # Check for comparison file first (most comprehensive)
    comparison_files = [
        os.path.join(current_output, 'cluster_visualization_comparison.html'),
        os.path.join(current_output, 'cluster_visualization_with_polygon_toggle.html')
    ]
    
    for filepath in comparison_files:
        if os.path.exists(filepath):
            html_files.append(filepath)
    
    # Check for individual algorithm files in current output
    for filename in ['cluster_visualization_pzwav.html', 'cluster_visualization_amico.html']:
        filepath = os.path.join(current_output, filename)
        if os.path.exists(filepath):
            html_files.append(filepath)
    
    # Check archive if no current files found
    if not html_files:
        for filename in os.listdir(archive_output) if os.path.exists(archive_output) else []:
            if filename.endswith('.html'):
                html_files.append(os.path.join(archive_output, filename))
    
    if not html_files:
        print("Error: No cluster visualization HTML files found!")
        print("Please run one of these first:")
        print("  python src/generate_standalone_html.py")
        print("  ./scripts/generate_all_algorithms.sh")
        return False
    
    # Show available files with descriptions
    print("Found visualization files:")
    for i, filename in enumerate(html_files, 1):
        file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
        if 'comparison' in filename:
            description = "(PZWAV + AMICO comparison)"
        elif 'pzwav' in filename:
            description = "(PZWAV algorithm)"
        elif 'amico' in filename:
            description = "(AMICO algorithm)"
        else:
            description = "(single algorithm)"
        print(f"  {i}. {filename} {description} ({file_size:.1f} MB)")
    
    # Determine which file to highlight
    main_file = html_files[0]  # Default to first available
    
    # Set up simple HTTP server
    # Change to project directory so we can serve all subdirectories
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)
    
    # Convert absolute path to relative path for URL
    main_file_relative = os.path.relpath(main_file, project_dir)
    
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            # Add CORS headers to allow local file access
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()
        
        def log_message(self, format, *args):
            # Suppress log messages for cleaner output
            return
    
    try:
        with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
            print(f"Starting simple HTTP server on port {port}")
            print(f"Main visualization: http://localhost:{port}/{main_file_relative}")
            print(f"Directory listing: http://localhost:{port}")
            print("Press Ctrl+C to stop the server")
            
            # Auto-open browser
            if auto_open:
                try:
                    webbrowser.open(f'http://localhost:{port}/{main_file_relative}')
                    print("Opening browser...")
                except:
                    print("Could not auto-open browser. Please open the URL manually.")
            
            print("-" * 50)
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        return True
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Error: Port {port} is already in use!")
            print(f"Try a different port: python {sys.argv[0]} --port {port+1}")
            return False
        else:
            print(f"Error starting server: {e}")
            return False

def main():
    """Main function with argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Serve cluster visualization HTML file')
    parser.add_argument('--port', type=int, default=8000, help='Port to serve on (default: 8000)')
    parser.add_argument('--no-browser', action='store_true', help='Do not auto-open browser')
    parser.add_argument('--generate', action='store_true', help='Generate HTML file first')
    
    args = parser.parse_args()
    
    # Generate HTML if requested
    if args.generate:
        print("Generating HTML file first...")
        try:
            import subprocess
            result = subprocess.run([sys.executable, 'src/generate_standalone_html.py'], 
                                  capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
            if result.returncode == 0:
                print("✓ HTML file generated successfully")
            else:
                print(f"✗ Error generating HTML: {result.stderr}")
                return
        except Exception as e:
            print(f"✗ Error running generator: {e}")
            return
    
    # Serve the file
    success = serve_visualization(port=args.port, auto_open=not args.no_browser)
    
    if success:
        print("✓ Server completed successfully")
    else:
        print("✗ Server failed to start")

if __name__ == '__main__':
    main()
