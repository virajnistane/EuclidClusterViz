#!/bin/bash

# Generate Standalone HTML Visualization
# Creates an interactive HTML file with cluster detection data

echo "=== Cluster Visualization HTML Generator ==="

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_DIR/src"

# Check if we can find the generator script
if [ ! -f "$SRC_DIR/generate_standalone_html.py" ]; then
    echo "Error: generate_standalone_html.py not found in $SRC_DIR"
    echo "Please ensure the script is in the src/ directory"
    exit 1
fi

echo "Generating interactive HTML visualization..."
echo "This may take a few moments to load and process all data..."
echo ""

# Change to project directory and run the generator
cd "$PROJECT_DIR"
python src/generate_standalone_html.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Success! Visualization generated successfully."
    echo ""
    echo "To view the visualization:"
    echo "1. Check the output/current/ directory for the HTML file"
    echo "2. Open the HTML file directly in your browser"
    echo ""
    echo "Features:"
    echo "- Interactive zoom and pan"
    echo "- Toggle between basic and detailed views"  
    echo "- Hover information for all data points"
    echo "- Color-coded tiles and MER polygons"
    echo "- Responsive design for different screen sizes"
else
    echo ""
    echo "✗ Error generating visualization."
    echo "Please check the error messages above and ensure all data files are accessible."
fi
