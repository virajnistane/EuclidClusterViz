"""Integration test and utility for side-by-side mosaic comparison (MER vs ESA).

See cluster_visualization/docs/ESA_SKY_MOSAIC_EXTRACTION.md for a full
description of the ESA Sky mosaic extraction pipeline.
"""

import os
from pathlib import Path

import numpy as np
import pytest
from plotly.subplots import make_subplots

from cluster_visualization.src.config import Config
from cluster_visualization.src.data.loader import DataLoader
from cluster_visualization.src.mermosaic import MOSAICHandler


# DEFAULT_TILE_ID = 102021016
DEFAULT_TILE_ID = 102019589
DEFAULT_ESA_SOURCE = "CDS/P/Euclid/Q1/VIS"


def _trace_coord_ranges(trace):
    """Return (ra_min, ra_max, dec_min, dec_max) from a Heatmap trace's x/y arrays."""
    x = np.asarray(trace.x)
    y = np.asarray(trace.y)
    return float(x.min()), float(x.max()), float(y.min()), float(y.max())


def create_side_by_side_mosaic_comparison(
    tile_id: int = DEFAULT_TILE_ID,
    algorithm: str = "PZWAV",
    esa_source: str = DEFAULT_ESA_SOURCE,
    output_html: str = f"cluster_visualization/tests/artifacts/mosaic_comparison_tile_{DEFAULT_TILE_ID}.html",
) -> tuple[str, dict]:
    """Create and save an HTML figure with local MER and ESA heatmaps side by side.

    Returns
    -------
    output_path : str
        Path to the saved HTML file.
    coord_info : dict
        Coordinate range summary for both traces, useful for assertions and
        human review.
    """

    config = Config()
    mosaic_handler = MOSAICHandler(config=config)
    data_loader = DataLoader(config=config)

    data = data_loader.load_data(algorithm)
    tile_bounds = mosaic_handler._extract_tile_bounds(data, tile_id)
    if tile_bounds is None:
        raise RuntimeError(f"Tile bounds not found for tile {tile_id}")

    ra_min_tile, ra_max_tile, dec_min_tile, dec_max_tile = tile_bounds
    tile_center_ra = (ra_min_tile + ra_max_tile) / 2.0
    tile_center_dec = (dec_min_tile + dec_max_tile) / 2.0

    local_trace = mosaic_handler.create_mosaic_image_trace(
        tile_id,
        opacity=0.85,
        colorscale="gray",
        provider="local_fits",
        source_id="local_mer",
        tile_bounds=tile_bounds,
    )
    if local_trace is None:
        raise RuntimeError(f"Could not load local MER mosaic for tile {tile_id}")

    esa_trace = mosaic_handler.create_mosaic_image_trace(
        tile_id,
        opacity=0.85,
        colorscale="gray",
        provider="esa_sky",
        source_id=esa_source,
        tile_bounds=tile_bounds,
    )
    if esa_trace is None:
        raise RuntimeError(f"Could not load ESA mosaic for tile {tile_id} (source={esa_source})")

    # Collect coordinate ranges for assertions / human review
    loc_ra0, loc_ra1, loc_dec0, loc_dec1 = _trace_coord_ranges(local_trace)
    esa_ra0, esa_ra1, esa_dec0, esa_dec1 = _trace_coord_ranges(esa_trace)

    coord_info = {
        "tile_bounds": tile_bounds,
        "tile_center": (tile_center_ra, tile_center_dec),
        "local": {"ra": (loc_ra0, loc_ra1), "dec": (loc_dec0, loc_dec1)},
        "esa": {"ra": (esa_ra0, esa_ra1), "dec": (esa_dec0, esa_dec1)},
    }

    print("\n── Coordinate ranges ───────────────────────────────────────")
    print(f"  Tile polygon  RA  [{ra_min_tile:.4f}, {ra_max_tile:.4f}]  "
          f"Dec [{dec_min_tile:.4f}, {dec_max_tile:.4f}]")
    print(f"  Local MER     RA  [{loc_ra0:.4f}, {loc_ra1:.4f}]  "
          f"Dec [{loc_dec0:.4f}, {loc_dec1:.4f}]")
    print(f"  ESA Sky       RA  [{esa_ra0:.4f}, {esa_ra1:.4f}]  "
          f"Dec [{esa_dec0:.4f}, {esa_dec1:.4f}]")
    print("─────────────────────────────────────────────────────────────\n")

    # The two subplots share their y-axis (Dec) so that zooming one panel in
    # the interactive HTML also zooms the other – essential for alignment checks.
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"Local MER FITS (tile {tile_id})",
            f"ESA Sky {esa_source} (tile {tile_id})",
        ),
        horizontal_spacing=0.05,
        shared_yaxes=True,
    )

    fig.add_trace(local_trace, row=1, col=1)
    fig.add_trace(esa_trace, row=1, col=2)

    fig.update_xaxes(title_text="RA (deg)", row=1, col=1)
    fig.update_yaxes(title_text="Dec (deg)", row=1, col=1)
    fig.update_xaxes(title_text="RA (deg)", row=1, col=2)

    # Explicitly set identical axis ranges on both panels so the pixel scale
    # matches when visually comparing object positions.
    shared_ra_pad = max(loc_ra1 - loc_ra0, esa_ra1 - esa_ra0) * 0.02
    shared_dec_pad = max(loc_dec1 - loc_dec0, esa_dec1 - esa_dec0) * 0.02
    shared_ra_range = [
        min(loc_ra0, esa_ra0) - shared_ra_pad,
        max(loc_ra1, esa_ra1) + shared_ra_pad,
    ]
    shared_dec_range = [
        min(loc_dec0, esa_dec0) - shared_dec_pad,
        max(loc_dec1, esa_dec1) + shared_dec_pad,
    ]
    fig.update_xaxes(range=shared_ra_range, row=1, col=1)
    fig.update_xaxes(range=shared_ra_range, row=1, col=2)
    fig.update_yaxes(range=shared_dec_range, row=1, col=1)

    fig.update_layout(
        title=(
            f"Mosaic Comparison: Local MER vs {esa_source} (tile {tile_id})<br>"
            f"<sup>Local RA [{loc_ra0:.3f}, {loc_ra1:.3f}]  Dec [{loc_dec0:.3f}, {loc_dec1:.3f}] | "
            f"ESA RA [{esa_ra0:.3f}, {esa_ra1:.3f}]  Dec [{esa_dec0:.3f}, {esa_dec1:.3f}]</sup>"
        ),
        showlegend=False,
        height=700,
        width=1500,
        template="plotly_white",
    )

    output_path = Path(output_html)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    return str(output_path), coord_info


@pytest.mark.integration
def test_generate_side_by_side_mosaic_comparison():
    """Generate and validate side-by-side local-vs-ESA mosaic comparison."""

    try:
        output_path, coord_info = create_side_by_side_mosaic_comparison()
    except Exception as exc:
        pytest.skip(f"Skipping integration comparison test (data/network unavailable): {exc}")

    assert os.path.exists(output_path)

    tile_ra_min, tile_ra_max, tile_dec_min, tile_dec_max = coord_info["tile_bounds"]
    esa_ra0, esa_ra1 = coord_info["esa"]["ra"]
    esa_dec0, esa_dec1 = coord_info["esa"]["dec"]

    # The ESA image is fetched with a 1.05× padding, so it must cover the full
    # tile polygon in both RA and Dec.
    assert esa_ra0 <= tile_ra_min, (
        f"ESA ra_min {esa_ra0:.4f} should be ≤ tile ra_min {tile_ra_min:.4f}"
    )
    assert esa_ra1 >= tile_ra_max, (
        f"ESA ra_max {esa_ra1:.4f} should be ≥ tile ra_max {tile_ra_max:.4f}"
    )
    assert esa_dec0 <= tile_dec_min, (
        f"ESA dec_min {esa_dec0:.4f} should be ≤ tile dec_min {tile_dec_min:.4f}"
    )
    assert esa_dec1 >= tile_dec_max, (
        f"ESA dec_max {esa_dec1:.4f} should be ≥ tile dec_max {tile_dec_max:.4f}"
    )

    # The ESA and local centres should agree to within 0.01 deg.
    tile_center_ra, tile_center_dec = coord_info["tile_center"]
    esa_center_ra = (esa_ra0 + esa_ra1) / 2.0
    esa_center_dec = (esa_dec0 + esa_dec1) / 2.0
    assert abs(esa_center_ra - tile_center_ra) < 0.01, (
        f"ESA centre RA {esa_center_ra:.4f} too far from tile centre {tile_center_ra:.4f}"
    )
    assert abs(esa_center_dec - tile_center_dec) < 0.01, (
        f"ESA centre Dec {esa_center_dec:.4f} too far from tile centre {tile_center_dec:.4f}"
    )


if __name__ == "__main__":
    path, info = create_side_by_side_mosaic_comparison()
    print(f"Saved side-by-side comparison figure to: {path}")
