#!/usr/bin/env python3
"""
Emergency HTTP Server for Cluster Visualization
A minimal server that should work from anywhere

REQUIREMENTS:
- EDEN environment: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
"""

import os
import sys
import http.server
import socketserver
import webbrowser

def check_environment():
    """Check if EDEN environment is activated"""
    eden_path = "/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1"
    if eden_path not in os.environ.get('PATH', ''):
        print("⚠️  WARNING: EDEN environment not detected!")
        print("   For full functionality, activate EDEN environment:")
        print(f"   source {eden_path}/bin/activate")
        print("")
        return False
    return True

def main():
    # Check environment
    check_environment()
    
    # Get script directory and project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    cluster_viz_dir = os.path.join(project_root, 'cluster_visualization')
    
    # Get project directory from command line or use default
    if len(sys.argv) > 1 and sys.argv[1].startswith('/'):
        project_dir = sys.argv[1]
    else:
        # Default to the cluster visualization directory
        project_dir = cluster_viz_dir
    
    # Port
    port = 8000
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except:
            pass
    
    print(f"Emergency HTTP Server for Cluster Visualization")
    print(f"Project directory: {project_dir}")
    print(f"Port: {port}")
    
    # Check if project directory exists
    if not os.path.exists(project_dir):
        print(f"Error: Project directory does not exist: {project_dir}")
        return
    
    # Change to project directory
    original_dir = os.getcwd()
    os.chdir(project_dir)
    
    # Look for HTML files
    html_files = []
    output_current = os.path.join('output', 'current')
    if os.path.exists(output_current):
        for f in os.listdir(output_current):
            if f.endswith('.html'):
                html_files.append(os.path.join('output', 'current', f))
    
    if not html_files:
        print("No HTML files found in output/current/")
        print("Please generate HTML files first:")
        print("  cd " + project_dir)
        print("  python src/generate_standalone_html.py")
        return
    
    print(f"Found {len(html_files)} HTML files")
    for f in html_files:
        print(f"  - {f}")
    
    main_file = html_files[0]
    
    try:
        # Start simple server
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"Serving at http://localhost:{port}")
            print(f"Main file: http://localhost:{port}/{main_file}")
            print("Press Ctrl+C to stop")
            
            # Try to open browser
            try:
                webbrowser.open(f'http://localhost:{port}/{main_file}')
            except:
                pass
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        os.chdir(original_dir)

if __name__ == '__main__':
    main()
