#!/bin/bash

# Generate Cluster Visualizations for Both Algorithms
# This script creates HTML visualizations for both PZWAV and AMICO algorithms

echo "=== Cluster Visualization Generator ==="
echo "Generating visualizations for both algorithms..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_DIR/src"

# Change to project directory for consistent execution
cd "$PROJECT_DIR"

# Check if we can find the generator script
if [ ! -f "$SRC_DIR/generate_standalone_html.py" ]; then
    echo "Error: generate_standalone_html.py not found in $SRC_DIR"
    echo "Please ensure the script is in the src/ directory"
    exit 1
fi

# Function to generate visualization for an algorithm
generate_viz() {
    local algorithm=$1
    local output_file="cluster_visualization_${algorithm,,}.html"
    
    echo ""
    echo "Generating visualization for $algorithm..."
    echo "Output file: $output_file"
    
    python src/generate_standalone_html.py --algorithm $algorithm --output $output_file
    
    if [ $? -eq 0 ]; then
        echo "✓ $algorithm visualization completed successfully"
        output_path="output/current/$output_file"
        if [ -f "$output_path" ]; then
            file_size=$(ls -lh "$output_path" | awk '{print $5}')
            echo "  File saved: $output_path"
            echo "  File size: $file_size"
        fi
    else
        echo "✗ $algorithm visualization failed"
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo ""
    echo "Usage options:"
    echo "  $0                    # Generate both PZWAV and AMICO"
    echo "  $0 pzwav             # Generate only PZWAV"
    echo "  $0 amico             # Generate only AMICO"
    echo "  $0 interactive       # Interactive mode"
    echo "  $0 help              # Show this help"
    echo ""
    echo "Generated files will be saved to: output/current/"
}

# Parse command line arguments
case "${1,,}" in
    "pzwav")
        generate_viz "PZWAV"
        ;;
    "amico")
        generate_viz "AMICO"
        ;;
    "interactive")
        echo "Running in interactive mode..."
        python src/generate_standalone_html.py --interactive
        ;;
    "help"|"-h"|"--help")
        show_usage
        exit 0
        ;;
    "")
        # Default: generate both
        echo "Generating visualizations for both algorithms..."
        generate_viz "PZWAV"
        generate_viz "AMICO"
        
        echo ""
        echo "=== Summary ==="
        output_pzwav="output/current/cluster_visualization_pzwav.html"
        output_amico="output/current/cluster_visualization_amico.html"
        
        if [ -f "$output_pzwav" ] && [ -f "$output_amico" ]; then
            echo "✓ Both visualizations generated successfully:"
            echo "  - $output_pzwav"
            echo "  - $output_amico"
            echo ""
            echo "You can now:"
            echo "  firefox $output_pzwav &  # Open PZWAV directly"
            echo "  firefox $output_amico &  # Open AMICO directly"
        else
            echo "✗ Some visualizations failed to generate"
            echo "Expected files:"
            echo "  - $output_pzwav (exists: $([ -f "$output_pzwav" ] && echo 'yes' || echo 'no'))"
            echo "  - $output_amico (exists: $([ -f "$output_amico" ] && echo 'yes' || echo 'no'))"
        fi
        ;;
    *)
        echo "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac
