#!/usr/bin/env python3
"""
Match a whole galaxy catalog to CATRED without running the Dash app.

Uses a catalog added in the app (Galaxy catalogs section; saved in
~/.config/clusterviz/catalogs.json) and the same matching as the app's
"Load CATRED near shown catalogs" button (src/data/catalog_matcher.py):
by OBJECT_ID when the catalog maps it, else each galaxy's nearest CATRED
source within the radius. The catalog is processed in groups (MER tile when
TILE_ID is mapped, else cluster when CLUSTER_ID is, else sky cells), so only
the CATRED tiles of one group are loaded at a time.

Usage:
    python generate_catalog_catred_matches.py --list
    python generate_catalog_catred_matches.py "NED spec-z"
    python generate_catalog_catred_matches.py euclid_spec_z --output matches.fits
    python generate_catalog_catred_matches.py "NED spec-z" --config config_local.ini --radius-arcsec 5

Without --output, rows are added to the catalog's match file
(<catalog>_catalogMatches.fits next to it, or under ~/.cache/clusterviz_catalogs/matches/),
replacing earlier rows for the same galaxies. With --output, a new file is written.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd  # type: ignore[import]
from astropy.table import Table  # type: ignore[import]

# Add project root (for the cluster_visualization package) and src (for
# sibling imports like config/data.*) to sys.path, as cluster_dash_app.py does.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

src_path = os.path.join(project_root, "cluster_visualization", "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from config import get_config  # noqa: E402
from data.catred_handler import CATREDHandler  # noqa: E402
from data.loader import DataLoader  # noqa: E402

from cluster_visualization.src.data.catalog_matcher import (  # noqa: E402
    match_by_id,
    match_by_position,
    match_file_path,
    write_matches,
)
from cluster_visualization.src.data.catalog_registry import CatalogRegistry  # noqa: E402
from cluster_visualization.src.data.galaxy_catalog import CLUSTER  # noqa: E402


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Match a galaxy catalog from the app's Galaxy catalogs list to CATRED.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("catalog", nargs="?", help="Catalog name or id (see --list)")
    parser.add_argument("--list", action="store_true", help="List the catalogs and exit")
    parser.add_argument(
        "--output", type=str, help="Write a new FITS file here instead of the catalog's match file"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=os.path.join(project_root, "config.ini"),
        help="Path to a config file (default: config.ini at the repo root)",
    )
    parser.add_argument(
        "--registry",
        type=str,
        help="Catalog list to read (default: ~/.config/clusterviz/catalogs.json)",
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        default="BOTH",
        choices=["PZWAV", "AMICO", "BOTH"],
        help="Cluster detection algorithm whose data to load (default: BOTH)",
    )
    parser.add_argument(
        "--radius-arcsec", type=float, default=1.0, help="Position match radius (default: 1.0)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Effective coverage threshold for masked CATRED loading (default: 0.8)",
    )
    parser.add_argument(
        "--maglim", type=float, default=24.0, help="Magnitude limit for CATRED (default: 24.0)"
    )
    parser.add_argument(
        "--unmasked", action="store_true", help="Load CATRED unmasked instead of coverage-masked"
    )
    parser.add_argument(
        "--cell-deg",
        type=float,
        default=1.0,
        help="Sky cell size for grouping when neither TILE_ID nor CLUSTER_ID is mapped (default: 1.0)",
    )
    return parser.parse_args()


def find_catalog(registry, wanted):
    """Spec whose id or name (case-insensitive) is ``wanted``."""
    wanted_lower = wanted.strip().lower()
    for spec in registry.list():
        if spec.id == wanted or spec.name.strip().lower() == wanted_lower:
            return spec
    return None


def groups(df, cell_deg):
    """(label, grouped rows) that keep each CATRED load small."""
    if "TILE_ID" in df.columns:
        return "MER tile", df.groupby("TILE_ID")
    if "CLUSTER_ID" in df.columns:
        return "cluster", df.groupby("CLUSTER_ID")
    dec_cell = np.floor(df["DEC"].to_numpy() / cell_deg)
    cos_dec = np.cos(np.radians((dec_cell + 0.5) * cell_deg)).clip(0.05)
    ra_cell = np.floor(df["RA"].to_numpy() * cos_dec / cell_deg)
    return "sky cell", df.groupby([dec_cell, ra_cell])


def main():
    args = parse_arguments()
    registry = CatalogRegistry(args.registry)

    if args.list or not args.catalog:
        specs = registry.list()
        if not specs:
            print(f"No catalogs in {registry.path}; add one in the app's External catalogs section.")
        for spec in specs:
            method = "OBJECT_ID" if "OBJECT_ID" in spec.columns else "position"
            print(f"{spec.id:24s} {spec.name:30s} {method:9s} {spec.path}")
        if not args.list:
            sys.exit("\nGive a catalog name or id.")
        return

    spec = find_catalog(registry, args.catalog)
    if spec is None:
        sys.exit(f"No catalog '{args.catalog}' in {registry.path} (see --list).")
    if spec.kind == CLUSTER:
        sys.exit(f"'{spec.name}' is a cluster catalog; CATRED matches are for galaxy catalogs.")
    catalog = registry.catalog(spec.id)
    if not catalog.is_available():
        sys.exit(f"Catalog '{spec.name}': {catalog.status}")
    df = catalog.get_all()
    by_id = "OBJECT_ID" in df.columns
    print(
        f"Catalog '{spec.name}': {catalog.status}; matching by {'OBJECT_ID' if by_id else 'position'}"
    )

    config = get_config(config_file=args.config)
    data_loader = DataLoader(config)
    catred_handler = CATREDHandler()
    print(f"Loading {args.algorithm} cluster data...")
    data = data_loader.load_data(args.algorithm)

    label, grouped = groups(df, args.cell_deg)
    n_groups = grouped.ngroups
    all_rows = []
    for n, (key, group) in enumerate(grouped, start=1):
        group = group.reset_index(drop=True)
        if by_id:
            result = match_by_id(group, catred_handler, data)
        else:
            result = match_by_position(
                group,
                catred_handler,
                data,
                args.radius_arcsec,
                not args.unmasked,
                args.threshold,
                args.maglim,
            )
        n_matched = 0 if result is None else len(result.rows)
        if n_matched:
            all_rows.append(result.rows)
        print(
            f"[{n}/{n_groups}] {label} {key}: {len(group)} galaxies, {n_matched} matched "
            f"(running total: {sum(len(r) for r in all_rows)})"
        )

    if not all_rows:
        sys.exit("No CATRED matches found - nothing written.")
    combined = pd.concat(all_rows, ignore_index=True)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        Table.from_pandas(combined).write(args.output, overwrite=True)
        output = args.output
    else:
        output = write_matches(spec, combined) or match_file_path(spec)
    print(f"\nDone: {len(combined)} matched galaxies out of {len(df)} written to {output}")


if __name__ == "__main__":
    main()
