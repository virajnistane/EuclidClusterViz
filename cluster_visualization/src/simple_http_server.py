#!/usr/bin/env python3
"""
Standalone Simple HTTP Server for Cluster Visualization
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
    
    print("=== Cluster Visualization HTTP Server ===")
    
    # Get the script directory and project directory
    script_dir = Path(__file__).parent.absolute()
    project_dir = script_dir.parent
    
    # Check for available HTML files in output directories
    html_files = []
    
    # Define search paths
    current_output = project_dir / 'output' / 'current'
    archive_output = project_dir / 'output' / 'archive'
    
    # Search for HTML files
    search_paths = [current_output, archive_output]
    
    for search_path in search_paths:
        if search_path.exists():
            for html_file in search_path.glob('*.html'):
                html_files.append(str(html_file))
    
    if not html_files:
        print("Error: No cluster visualization HTML files found!")
        print(f"Searched in:")
        for search_path in search_paths:
            print(f"  - {search_path}")
        print("")
        print("Please run one of these first:")
        print("  python src/generate_standalone_html.py")
        print("  ./scripts/generate_all_algorithms.sh")
        return False
    
    # Display found files
    print("Found visualization files:")
    for i, filepath in enumerate(html_files, 1):
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # Convert to MB
        
        # Determine file type based on filename
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
    os.chdir(str(project_dir))
    
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
    parser.add_argument('--port', type=int, default=8000, 
                       help='Port to serve on (default: 8000)')
    parser.add_argument('--no-browser', action='store_true',
                       help='Do not auto-open browser')
    parser.add_argument('--generate', action='store_true',
                       help='Generate HTML file first')
    
    args = parser.parse_args()
    
    # Generate HTML first if requested
    if args.generate:
        print("Generating HTML file first...")
        try:
            # Import and run the generator
            sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))
            from generate_standalone_html import main as generate_main
            generate_main()
        except Exception as e:
            print(f"Error generating HTML: {e}")
            print("Please run manually: python src/generate_standalone_html.py")
            return
    
    # Start server
    serve_visualization(port=args.port, auto_open=not args.no_browser)

if __name__ == '__main__':
    main()
