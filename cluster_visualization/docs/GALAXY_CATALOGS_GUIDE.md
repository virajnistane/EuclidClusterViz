# Galaxy Catalogs Guide

Put any galaxy catalog on the sky map: a NED spec-z cross-match, the Euclid spec-z
galaxy catalogue, or a table from any other survey. You tell the app which of the
catalog's columns hold the right ascension, declination, redshift and so on, and it
does the rest: markers with hover details, CATRED sources matched to the galaxies,
the catalog's spec-z next to each source's photometric p(z), and a cluster filter.

Catalogs are added in the app, not in the config file, and are kept per user.

## Adding a catalog

Open the **Galaxy catalogs** section of the sidebar and press **Add catalog**.

1. **File.** Type the path of the catalog on the cluster (for example
   `/sps/euclid/Users/.../catalog.fits`) and press **Read columns** (or Enter).
   Supported: FITS (`.fits`, `.fit`, `.fts`, `.fits.gz`), CSV, ECSV and Parquet.
   Only the column list is read at this point, so even a large file opens at once.
   A FITS file with several tables gets a **Table** picker.
2. **Columns.** Each standard column has a dropdown listing the file's columns of
   a suitable type. Common names are filled in for you; check them, and leave
   empty what the catalog does not have. Each line says what a mapping turns on.
3. **Options.** Optionally keep only the rows where a true/false column is true
   (**Keep only rows where**, e.g. a quality flag), pick extra columns to show on
   hover, and set the name, colour and marker shape.
4. **Check** shows the row count and the RA/Dec range of the first rows, and any
   problem: a missing RA or Dec, a column of the wrong type, Dec outside ±90°,
   RA outside 0–360°, or RA that looks like hours. **Save** adds the catalog
   (it refuses while there are errors).

The pen next to a catalog reopens this dialog with its mapping; the bin removes
the catalog from the list (the file itself is never touched).

### Standard columns

| Column | Required | Type | Turns on |
|---|---|---|---|
| Right ascension (deg) | yes | number | markers, viewport, position match |
| Declination (deg) | yes | number | markers, viewport, position match |
| Source ID | no | integer or text | hover; key of the match file |
| Euclid MER OBJECT_ID | no | integer | exact CATRED match by ID; p(z) when clicking a marker |
| MER tile ID | no | integer | faster OBJECT_ID lookup (opens that tile first) |
| Spectroscopic redshift | no | number | hover; line on the p(z) plot; match file |
| Spec-z uncertainty | no | number | hover; band around the p(z) line |
| Spec-z quality flag | no | any | hover |
| Photometric redshift | no | number | hover; match file |
| Merged cluster ID (`ID_UNIQUE_CLUSTER`) | no | integer | the "Spec-z verification" cluster filter |

The tags next to a catalog in the list show what it can do: **ID** (OBJECT_ID
mapped), **spec-z** and **clusters** (cluster IDs mapped).

### Examples

**NED spec-z cross-match** (`ned_specz_tr1fsouth.fits`, one row per galaxy and cluster):

| Standard column | Catalog column |
|---|---|
| Right ascension | `RA` |
| Declination | `DEC` |
| Spectroscopic redshift | `Z` |
| Spec-z uncertainty | `ZUNC` |
| Spec-z quality flag | `ZFLAG` |
| Merged cluster ID | `ID_UNIQUE_CLUSTER` |
| Also show on hover | `ZREF`, `R_MPC` (optional) |

**Euclid spec-z galaxy catalogue** (`euclid_wide_survey_noduplicates_galaxy_catalogue.fits`):

| Standard column | Catalog column |
|---|---|
| Right ascension | `right_ascension` |
| Declination | `declination` |
| Euclid MER OBJECT_ID | `object_id` |
| MER tile ID | `tile_index` |
| Spectroscopic redshift | `z_spec_median_good` |
| Spec-z uncertainty | `z_spec_sigma_good` |
| Keep only rows where | `has_z_spec_good` |

All of these are filled in automatically when the file is read.

## Showing a catalog

Switch a catalog on to draw it. Its markers sit above CATRED and below the
clusters; hovering one shows the mapped columns and the extra hover columns.
The line under the switch gives the row count once loaded, for example
"264,111 galaxies of 445,702 (where has_z_spec_good)", or the reason it could not
be loaded.

**Large catalogs.** A catalog with more than 10,000 rows is drawn for the current
view only, plus half a view on each side, and redrawn after every zoom or pan.
If that area still holds more than 10,000 galaxies, 10,000 of them are drawn
(always the same ones for the same view) and the legend says so, e.g.
"Catalog: Euclid spec-z (10,000 of 38,214 here)". This keeps the plot quick over
the SSH tunnel.

**First load.** The first time a catalog is shown, the app reads its mapped
columns. FITS tables are stored row by row, so this reads the whole file once
(the 617 MB Euclid catalogue takes about 1.5 minutes over sshfs, much less on
`/sps`). The columns are then cached in `~/.cache/clusterviz_catalogs/` and later
loads take a fraction of a second. The cache is rebuilt when the file or the
mapping changes.

Shown catalogs also appear in the Aladin view, one layer each, in their own
colour and marker shape.

## CATRED sources near the shown catalogs

Zoom in to under 2° × 2° and press **Load CATRED near shown catalogs**. For each
shown catalog, the galaxies in view are matched to CATRED and the matched sources
are marked with hollow squares in the catalog's colour. A line per catalog reports
the result.

- **By OBJECT_ID** (catalog maps OBJECT_ID): exact. The app looks in the galaxy's
  MER tile first (when the tile ID is mapped), then in the tiles around the
  galaxies. The match radius and the Mask section's coverage and magnitude
  settings are not used. Example: "Euclid spec-z: 412 of 415 galaxies found by OBJECT_ID".
- **By position** (no OBJECT_ID): the CATRED sources within the **Match radius**
  of the galaxies, loaded with the Mask section's masked mode, coverage threshold
  and magnitude limit. Example: "NED spec-z: 37 CATRED sources within 3.0″ of 41
  galaxies".

Switching a catalog off also removes its matches.

### p(z) with the spec-z

Click a matched source: the PHZ Analysis tab shows its photometric p(z) with the
catalog galaxy's spec-z as a dashed line (and a shaded ± band when the
uncertainty is mapped), labelled with the catalog name. For a position match the
spec-z is that of the nearest catalog galaxy.

For a catalog with OBJECT_ID mapped you can also click the catalog marker itself:
its CATRED source is looked up by ID and shown the same way, without pressing the
match button first.

### Match file

Every match is also recorded in `<catalog file name>_catalogMatches.fits`, next to
the catalog file, or in `~/.cache/clusterviz_catalogs/matches/` when that folder is
not writable. One row per matched galaxy:

| Column | Meaning |
|---|---|
| `SOURCE_ID`, `OBJECT_ID`, `CLUSTER_ID`, `SPEC_Z`, `SPEC_Z_ERR`, `PHOT_Z` | the catalog's values, when mapped |
| `RA`, `DEC` | the catalog galaxy |
| `CATRED_RA`, `CATRED_DEC` | its CATRED source |
| `PHZ_MEDIAN`, `PHZ_MODE` | the CATRED source's photometric redshift |
| `SEP_ARCSEC` | distance between the two positions |
| `MATCH_METHOD` | `object_id` or `position` |

Matching the same galaxy again (another zoom, or the batch script) replaces its
row. Rows are identified by the source ID (else the galaxy's RA/Dec) plus the
cluster ID when mapped, so a galaxy listed under two clusters keeps two rows.
If a changed mapping changes the columns, the file is started again.

### Whole catalog at once

To match a whole catalog without the app, use the batch script with a catalog
from your list (name or id):

```bash
python cluster_visualization/scripts/generate_catalog_catred_matches.py --list
python cluster_visualization/scripts/generate_catalog_catred_matches.py "NED spec-z" --config config_local.ini
python cluster_visualization/scripts/generate_catalog_catred_matches.py euclid_spec_z --output euclid_matches.fits
```

It uses the same matching as the button and works through the catalog in groups
(by MER tile when the tile ID is mapped, else by cluster, else by 1° sky cells),
so only a few CATRED tiles are in memory at a time. Without `--output` it adds to
the catalog's match file. Other options: `--radius-arcsec`, `--threshold`,
`--maglim`, `--unmasked`, `--algorithm`, `--cell-deg`, `--registry`.

## Cluster filter

**Filters → Spec-z verification** lists the catalogs that map cluster IDs, with
their cluster count. Choose one or more and press **Apply filters**: only the
merged clusters with galaxies in any chosen catalog stay on the map, in the globe
and in the cluster tools. Clear the choice and apply again to show all clusters.
The control is disabled until a catalog maps cluster IDs.

## Where things are kept

| What | Where |
|---|---|
| Your catalog list and mappings | `~/.config/clusterviz/catalogs.json` (`$XDG_CONFIG_HOME/clusterviz/` if set) |
| Cached catalog columns | `~/.cache/clusterviz_catalogs/` |
| Match files | next to each catalog, else `~/.cache/clusterviz_catalogs/matches/` |

The list is per user and shared by all your app instances; it is re-read when it
changes. Earlier versions set one NED catalog in the config (`[paths]
ned_specz_fits`); if an old config still has that key, its catalog is added to the
list once at startup and can then be managed here.

**Apptainer image.** `launch_sif.sh` binds `/sps` and your home (where the list
and caches live). For catalogs elsewhere, add their folder:
`CLUSTERVIZ_BIND=/path/to/catalogs ./launch_sif.sh`.

> **Security note:** the catalog path field can read any file your account can
> read. That is fine for the default instance, which only you reach through your
> SSH tunnel. If you start the app with `--external`, anyone who can reach the
> port can use this field too.
