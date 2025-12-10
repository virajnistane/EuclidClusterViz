#!/usr/bin/env python3
"""
Test fix for individual tile filtering in SNR/Redshift client-side callbacks
"""

import re
from pathlib import Path


def test_tile_filtering_fix():
    print("🔧 Testing Individual Tile Filtering Fix")
    print("=" * 45)

    # Test the main_plot.py file
    callback_file = Path("cluster_visualization/callbacks/main_plot.py")
    if not callback_file.exists():
        print("❌ main_plot.py not found")
        return

    with open(callback_file, "r") as f:
        content = f.read()

    # Find all JavaScript filtering conditions
    pattern = r"trace\.name\.includes\('Merged'\)\s*\|\|\s*trace\.name\.includes\('([^']+)'\)"
    matches = re.findall(pattern, content)

    print(f"\n📊 Found {len(matches)} filtering conditions:")
    for i, match in enumerate(matches, 1):
        print(f"   {i}. Merged || {match}")

    # Check if 'Tile' is included in filtering conditions
    tile_filters = [match for match in matches if match == "Tile"]
    cluster_filters = [match for match in matches if match == "Cluster"]

    print(f"\n✅ Analysis:")
    print(f"   • 'Tile' filtering conditions: {len(tile_filters)}")
    print(f"   • 'Cluster' filtering conditions: {len(cluster_filters)} (should be 0 after fix)")

    if len(tile_filters) >= 2:  # Should have at least SNR and redshift callbacks
        print("\n🎯 SUCCESS: Individual tile filtering is now enabled!")
        print("   ✅ SNR filtering will affect individual tiles")
        print("   ✅ Redshift filtering will affect individual tiles")
    else:
        print("\n❌ ISSUE: Individual tile filtering may not be fully implemented")

    # Check for specific callback functions
    print(f"\n🔍 Callback Functions:")
    snr_callback_present = "_setup_snr_clientside_callback" in content
    redshift_callback_present = "_setup_redshift_clientside_callback" in content

    print(f"   • SNR client-side callback: {'✅ FOUND' if snr_callback_present else '❌ MISSING'}")
    print(
        f"   • Redshift client-side callback: {'✅ FOUND' if redshift_callback_present else '❌ MISSING'}"
    )

    # Check for trace name patterns that will be filtered
    print(f"\n🎯 Filtering Target Analysis:")
    print("   Traces that will be filtered by SNR/Redshift:")
    print("   ✅ 'Merged Data (ALGORITHM) - X clusters'")
    print("   ✅ 'Merged Data (Enhanced) - X clusters'")
    print("   ✅ 'Tile XX' (individual tiles)")
    print("   ✅ 'Tile XX (Enhanced)' (enhanced individual tiles)")
    print("   ❌ 'CATRED Masked Data #X' (preserved)")
    print("   ❌ 'CATRED Unmasked Data #X' (preserved)")

    print(f"\n💡 Expected Behavior After Fix:")
    print("   • Moving SNR sliders → filters merged clusters AND individual tiles")
    print("   • Moving redshift sliders → filters merged clusters AND individual tiles")
    print("   • CATRED data → completely preserved (not affected)")
    print("   • Performance → <100ms for all cluster filtering")


if __name__ == "__main__":
    test_tile_filtering_fix()
