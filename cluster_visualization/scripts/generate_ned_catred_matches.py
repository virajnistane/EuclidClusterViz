#!/usr/bin/env python3
"""
Generate a NED-vs-CATRED match FITS file for the whole NED spec-z catalog,
without running the Dash app.

For every cluster in the configured ned_specz_fits catalog, auto-discovers
and loads the intersecting MER/CATRED tiles for that cluster's galaxies
only (never the whole survey's tiles at once), finds each galaxy's nearest
CATRED source within the given radius, and writes one row per matched
galaxy to the requested output file. This is the same matching logic used
by the interactive "Load CATRED near NED" button
(cluster_visualization/src/data/ned_catred_matcher.py), just run over the
entire catalog in one batch instead of one zoomed-in view at a time.

Usage:
    python generate_ned_catred_matches.py output.fits
    python generate_ned_catred_matches.py output.fits --config config_local.ini
    python generate_ned_catred_matches.py output.fits --algorithm AMICO --radius-arcsec 5

By default reads config.ini at the repo root; pass --config to use a
different file (e.g. config_local.ini).
"""

import argparse
import os
import sys

import pandas as pd  # type: ignore[import]
from astropy.table import Table  # type: ignore[import]

# Add project root (for the cluster_visualization package) and src (for
# sibling imports like config/data.*) to sys.path - mirrors
# cluster_visualization/src/cluster_dash_app.py:84-92.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

src_path = os.path.join(project_root, "cluster_visualization", "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from config import get_config  # noqa: E402
from data.catred_handler import CATREDHandler  # noqa: E402
from data.loader import DataLoader  # noqa: E402
from data.ned_catred_matcher import match_ned_to_catred  # noqa: E402
from data.ned_handler import NEDHandler  # noqa: E402


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate a NED-vs-CATRED nearest-match FITS file for the whole NED spec-z catalog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("output", type=str, help="Path to write the resulting FITS file to")
    parser.add_argument(
        "--config", type=str, default=os.path.join(project_root, "config.ini"),
        help="Path to a config file (default: config.ini at the repo root)",
    )
    parser.add_argument(
        "--algorithm", type=str, default="BOTH", choices=["PZWAV", "AMICO", "BOTH"],
        help="Cluster detection algorithm to load (default: BOTH)",
    )
    parser.add_argument(
        "--radius-arcsec", type=float, default=3.0,
        help="Match radius in arcsec (default: 3.0)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.8,
        help="Effective coverage threshold for masked CATRED loading (default: 0.8)",
    )
    parser.add_argument(
        "--maglim", type=float, default=24.0,
        help="Magnitude limit for CATRED filtering (default: 24.0)",
    )
    parser.add_argument(
        "--unmasked", action="store_true",
        help="Use unmasked CATRED loading instead of the default coverage-masked mode",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    config = get_config(config_file=args.config)
    ned_handler = NEDHandler(config)
    if not ned_handler.is_available():
        sys.exit("Error: ned_specz_fits is not configured or failed to load - check [paths] ned_specz_fits.")

    df = ned_handler.get_all_galaxies()
    cluster_ids = ned_handler.get_unique_cluster_ids()
    print(f"Loaded {len(df)} NED galaxies across {len(cluster_ids)} clusters")

    data_loader = DataLoader(config)
    catred_handler = CATREDHandler()
    print(f"Loading {args.algorithm} cluster data...")
    data = data_loader.load_data(args.algorithm)

    catred_masked = not args.unmasked
    all_rows = []
    for n, (cluster_id, group) in enumerate(df.groupby("ID_UNIQUE_CLUSTER"), start=1):
        group = group.reset_index(drop=True)
        result = match_ned_to_catred(
            group, catred_handler, data, args.radius_arcsec, catred_masked, args.threshold, args.maglim
        )
        n_matched = 0 if result is None else len(result.nearest_rows)
        if n_matched > 0:
            all_rows.append(result.nearest_rows)
        print(
            f"[{n}/{len(cluster_ids)}] cluster {cluster_id}: {len(group)} galaxies, "
            f"{n_matched} matched (running total: {sum(len(r) for r in all_rows)})"
        )

    if not all_rows:
        sys.exit("No CATRED matches found for any NED galaxy - nothing written.")

    combined = pd.concat(all_rows, ignore_index=True)
    Table.from_pandas(combined).write(args.output, overwrite=True)
    print(
        f"\nDone: {len(combined)} matched galaxies out of {len(df)} written to {args.output}"
    )


if __name__ == "__main__":
    main()
