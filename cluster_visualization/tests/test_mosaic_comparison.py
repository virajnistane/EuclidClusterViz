"""Integration test and utility for side-by-side mosaic comparison (MER vs ESA)."""

import os
from pathlib import Path

import pytest
from plotly.subplots import make_subplots

from cluster_visualization.src.config import Config
from cluster_visualization.src.data.loader import DataLoader
from cluster_visualization.src.mermosaic import MOSAICHandler


# DEFAULT_TILE_ID = 102021016
DEFAULT_TILE_ID = 102019589
DEFAULT_ESA_SOURCE = "CDS/P/Euclid/Q1/VIS"


def create_side_by_side_mosaic_comparison(
    tile_id: int = DEFAULT_TILE_ID,
    algorithm: str = "PZWAV",
    esa_source: str = DEFAULT_ESA_SOURCE,
    output_html: str = f"cluster_visualization/tests/artifacts/mosaic_comparison_tile_{DEFAULT_TILE_ID}.html",
) -> str:
    """Create and save an HTML figure with local MER and ESA DSS2 heatmaps side by side."""

    config = Config()
    mosaic_handler = MOSAICHandler(config=config)
    data_loader = DataLoader(config=config)

    data = data_loader.load_data(algorithm)
    tile_bounds = mosaic_handler._extract_tile_bounds(data, tile_id)
    if tile_bounds is None:
        raise RuntimeError(f"Tile bounds not found for tile {tile_id}")

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

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"Local MER FITS (tile {tile_id})",
            f"ESA Sky Euclid Q1 VIS (tile {tile_id})",
        ),
        horizontal_spacing=0.05,
    )

    fig.add_trace(local_trace, row=1, col=1)
    fig.add_trace(esa_trace, row=1, col=2)

    fig.update_xaxes(title_text="RA (deg)", row=1, col=1)
    fig.update_yaxes(title_text="Dec (deg)", row=1, col=1)
    fig.update_xaxes(title_text="RA (deg)", row=1, col=2)
    fig.update_yaxes(title_text="Dec (deg)", row=1, col=2)

    fig.update_layout(
        title=(
            "Mosaic Comparison: Local MER vs ESA Euclid Q1 VIS "
            f"(tile {tile_id})"
        ),
        showlegend=False,
        height=700,
        width=1500,
        template="plotly_white",
    )

    output_path = Path(output_html)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    return str(output_path)


@pytest.mark.integration
def test_generate_side_by_side_mosaic_comparison():
    """Generate side-by-side local-vs-ESA mosaic comparison for visual inspection."""

    try:
        output_path = create_side_by_side_mosaic_comparison()
    except Exception as exc:
        pytest.skip(f"Skipping integration comparison test (data/network unavailable): {exc}")

    assert os.path.exists(output_path)


if __name__ == "__main__":
    path = create_side_by_side_mosaic_comparison()
    print(f"Saved side-by-side comparison figure to: {path}")
