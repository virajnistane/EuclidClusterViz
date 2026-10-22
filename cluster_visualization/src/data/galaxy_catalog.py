"""
User-supplied galaxy catalogs (NED spec-z, Euclid spec-z, any survey).

A catalog is any table with sky positions. The app works with a fixed set of
standard roles (RA, DEC, SPEC_Z, ...); each catalog maps the roles it can fill
to its own column names, and everything downstream reads only the standard
names. A feature is available for a catalog when the roles it needs are mapped
(see GalaxyCatalog.capabilities).

Framework-independent - no Dash imports.
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd  # type: ignore[import]
from loguru import logger

# Column kinds, from the file's declared types
FLOAT, INT, BOOL, STR, ARRAY = "float", "int", "bool", "str", "array"
NUMERIC = (FLOAT, INT)

FITS_EXTENSIONS = (".fits", ".fit", ".fts", ".fits.gz", ".fit.gz")
CSV_EXTENSIONS = (".csv",)
ECSV_EXTENSIONS = (".ecsv",)
PARQUET_EXTENSIONS = (".parquet", ".pq")

# Rows read to check a mapping (RA/Dec ranges) without loading the table
SAMPLE_ROWS = 5000


@dataclass(frozen=True)
class Role:
    """A standard column the app understands."""

    name: str
    label: str
    kinds: Tuple[str, ...]  # column kinds that can fill this role
    required: bool
    enables: str  # shown next to the dropdown: what mapping this role turns on
    aliases: Tuple[str, ...]  # lower-case column names that prefill the dropdown, best first


ROLES: Tuple[Role, ...] = (
    Role(
        "RA",
        "Right ascension (deg)",
        NUMERIC,
        True,
        "markers, viewport, position match",
        (
            "ra",
            "right_ascension",
            "ra_deg",
            "radeg",
            "raj2000",
            "ra_j2000",
            "alpha_j2000",
            "ra_icrs",
        ),
    ),
    Role(
        "DEC",
        "Declination (deg)",
        NUMERIC,
        True,
        "markers, viewport, position match",
        (
            "dec",
            "declination",
            "dec_deg",
            "decdeg",
            "dej2000",
            "dec_j2000",
            "delta_j2000",
            "de_icrs",
        ),
    ),
    Role(
        "SOURCE_ID",
        "Source ID",
        (INT, STR),
        False,
        "hover; key of the CATRED match file",
        ("source_id", "id", "objid", "obj_id", "galaxy_id", "name"),
    ),
    Role(
        "OBJECT_ID",
        "Euclid MER OBJECT_ID",
        (INT,),
        False,
        "exact CATRED match by ID (no radius)",
        ("object_id",),
    ),
    Role(
        "TILE_ID",
        "MER tile ID",
        (INT,),
        False,
        "faster OBJECT_ID lookup (opens only that tile)",
        ("tile_index", "tile_id", "tileid", "mertileid"),
    ),
    Role(
        "SPEC_Z",
        "Spectroscopic redshift",
        NUMERIC,
        False,
        "hover; line on the p(z) plot; match file",
        ("z_spec_median_good", "z_spec", "zspec", "specz", "spec_z", "z_spec_median_all", "z"),
    ),
    Role(
        "SPEC_Z_ERR",
        "Spec-z uncertainty",
        NUMERIC,
        False,
        "hover; band around the p(z) line",
        ("z_spec_sigma_good", "zunc", "z_err", "zerr", "e_z", "z_spec_err", "sigma_z"),
    ),
    Role(
        "SPEC_Z_QUALITY",
        "Spec-z quality flag",
        (INT, FLOAT, STR, BOOL),
        False,
        "hover",
        ("zflag", "z_flag", "zqual", "z_qual", "z_quality", "zwarning"),
    ),
    Role(
        "PHOT_Z",
        "Photometric redshift",
        NUMERIC,
        False,
        "hover; match file",
        ("photo_z", "phot_z", "photz", "z_phot", "zphot", "phz_median"),
    ),
    Role(
        "CLUSTER_ID",
        "Merged cluster ID (ID_UNIQUE_CLUSTER)",
        (INT,),
        False,
        "'only clusters with a match' filter",
        ("id_unique_cluster", "cluster_id"),
    ),
)
ROLES_BY_NAME: Dict[str, Role] = {r.name: r for r in ROLES}
ROLE_NAMES = tuple(ROLES_BY_NAME)

# Boolean columns that prefill "keep only rows where ... is true"
SELECT_ALIASES = ("has_z_spec_good", "has_z_spec", "good", "use")


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    kind: str
    dtype: str
    unit: str = ""


@dataclass(frozen=True)
class TableInfo:
    """One table in a catalog file (a FITS file may hold several)."""

    hdu: Optional[int]  # FITS extension index; None for single-table formats
    name: str
    nrows: Optional[int]  # None when it would take a full read to count (CSV)
    columns: Tuple[ColumnInfo, ...]

    def column(self, name: str) -> Optional[ColumnInfo]:
        return next((c for c in self.columns if c.name == name), None)


@dataclass
class CatalogSpec:
    """A catalog as the user configured it; persisted by CatalogRegistry."""

    name: str
    path: str
    columns: Dict[str, str]  # role -> column name in the file
    hdu: Optional[int] = None
    select_column: Optional[str] = None  # keep only rows where this boolean column is true
    hover_columns: List[str] = field(default_factory=list)
    color: str = "#ff8800"
    symbol: str = "diamond"
    id: str = ""  # assigned by CatalogRegistry

    @classmethod
    def from_dict(cls, data: dict) -> "CatalogSpec":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        spec = cls(**known)
        spec.columns = {r: c for r, c in (spec.columns or {}).items() if r in ROLES_BY_NAME and c}
        spec.hover_columns = list(spec.hover_columns or [])
        return spec

    def to_dict(self) -> dict:
        return asdict(self)

    def used_columns(self) -> List[str]:
        """File columns this catalog reads, each once, in a stable order."""
        names = [self.columns[r] for r in ROLE_NAMES if r in self.columns]
        if self.select_column:
            names.append(self.select_column)
        names.extend(self.hover_columns)
        return list(dict.fromkeys(names))


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def file_format(path: str) -> Optional[str]:
    lower = path.lower()
    for fmt, exts in (
        ("fits", FITS_EXTENSIONS),
        ("csv", CSV_EXTENSIONS),
        ("ecsv", ECSV_EXTENSIONS),
        ("parquet", PARQUET_EXTENSIONS),
    ):
        if lower.endswith(exts):
            return fmt
    return None


def _kind_of(dtype: np.dtype) -> str:
    if dtype.shape:
        return ARRAY
    if np.issubdtype(dtype, np.bool_):
        return BOOL
    if np.issubdtype(dtype, np.integer):
        return INT
    if np.issubdtype(dtype, np.floating):
        return FLOAT
    return STR


def _arrow_kind(arrow_type) -> str:
    import pyarrow as pa  # type: ignore[import]

    if pa.types.is_boolean(arrow_type):
        return BOOL
    if pa.types.is_integer(arrow_type):
        return INT
    if pa.types.is_floating(arrow_type):
        return FLOAT
    if (
        pa.types.is_list(arrow_type)
        or pa.types.is_large_list(arrow_type)
        or pa.types.is_fixed_size_list(arrow_type)
    ):
        return ARRAY
    return STR


def _fits_kind(column) -> str:
    """Kind of a FITS table column; logical (L) columns declare an int8 dtype."""
    dtype = np.dtype(column.dtype)
    if not dtype.shape and str(column.format).upper().endswith("L"):
        return BOOL
    return _kind_of(dtype)


def _column_kind(values) -> str:
    """Kind of an in-memory column (astropy/pandas), multi-dimensional -> array."""
    arr = np.asarray(values)
    return ARRAY if arr.ndim > 1 else _kind_of(arr.dtype)


def inspect_columns(path: str) -> List[TableInfo]:
    """List the tables and columns of a catalog file, reading headers only.

    Raises ValueError for a missing, unreadable or unsupported file.
    """
    if not os.path.isfile(path):
        raise ValueError(f"file not found: {path}")
    if not os.access(path, os.R_OK):
        raise ValueError(f"file not readable: {path}")
    fmt = file_format(path)
    if fmt is None:
        raise ValueError(
            f"unsupported file type: {os.path.basename(path)} (use FITS, CSV, ECSV or Parquet)"
        )

    if fmt == "fits":
        from astropy.io import fits  # type: ignore[import]

        tables = []
        with fits.open(path, memmap=True) as hdul:
            for i, hdu in enumerate(hdul):
                if not isinstance(hdu, (fits.BinTableHDU, fits.TableHDU)):
                    continue
                cols = tuple(
                    ColumnInfo(c.name, _fits_kind(c), str(c.format), str(c.unit or ""))
                    for c in hdu.columns
                )
                tables.append(TableInfo(i, hdu.name or f"HDU {i}", hdu.header.get("NAXIS2"), cols))
        if not tables:
            raise ValueError(f"no table extension in {os.path.basename(path)}")
        return tables

    if fmt == "parquet":
        import pyarrow.parquet as pq  # type: ignore[import]

        pf = pq.ParquetFile(path)
        cols = tuple(ColumnInfo(f.name, _arrow_kind(f.type), str(f.type)) for f in pf.schema_arrow)
        return [TableInfo(None, os.path.basename(path), pf.metadata.num_rows, cols)]

    if fmt == "ecsv":
        from astropy.table import Table  # type: ignore[import]

        table = Table.read(path, format="ascii.ecsv")
        cols = tuple(
            ColumnInfo(n, _column_kind(table[n]), str(table[n].dtype), str(table[n].unit or ""))
            for n in table.colnames
        )
        return [TableInfo(None, os.path.basename(path), len(table), cols)]

    sample = pd.read_csv(path, nrows=SAMPLE_ROWS)
    cols = tuple(
        ColumnInfo(str(n), _column_kind(sample[n].to_numpy()), str(sample[n].dtype))
        for n in sample.columns
    )
    return [TableInfo(None, os.path.basename(path), None, cols)]


def find_table(tables: List[TableInfo], hdu: Optional[int]) -> TableInfo:
    """The table for ``hdu`` (the first table when hdu is None)."""
    if hdu is None:
        return tables[0]
    for t in tables:
        if t.hdu == hdu:
            return t
    raise ValueError(f"no table at HDU {hdu}")


def _native(values) -> np.ndarray:
    """FITS data is big-endian; pandas and scipy want native byte order."""
    values = np.array(values)
    if values.dtype.kind in "biuf" and not values.dtype.isnative:
        return values.astype(values.dtype.newbyteorder("="))
    return values


def _decode_fits_column(raw: np.ndarray, column) -> np.ndarray:
    """Raw binary-table field -> values, as astropy would give them."""
    fmt = str(column.format).upper()
    if not raw.dtype.shape and fmt.endswith("L"):
        return raw == ord("T")
    if raw.dtype.kind == "S":
        return np.char.rstrip(np.char.decode(raw, "ascii", errors="replace"))
    values = _native(raw)
    bscale, bzero = column.bscale, column.bzero
    if (
        bscale in (None, 1)
        and bzero not in (None, 0)
        and values.dtype.kind == "i"
        and bzero == 2 ** (8 * values.dtype.itemsize - 1)
    ):
        # Unsigned integers stored signed with an offset: flip the sign bit, exactly
        size = values.dtype.itemsize
        return values.view(f"u{size}") ^ np.array(1 << (8 * size - 1), dtype=f"u{size}")
    if bscale not in (None, 1) or bzero not in (None, 0):
        values = values * (bscale or 1) + (bzero or 0)
    return values


def _read_fits_rows(
    path: str, hdu_index: int, names: List[str], nrows: Optional[int]
) -> Optional[pd.DataFrame]:
    """Read ``names`` from an uncompressed binary table straight from the file, in chunks.

    astropy's ``hdu.data`` reads and converts the whole table before any column
    can be used (94 s for the 617 MB Euclid catalog over sshfs); this reads only
    the rows asked for. Returns None for layouts it does not handle (compressed
    files, ASCII tables, variable-length arrays) so the caller falls back to astropy.
    """
    from astropy.io import fits  # type: ignore[import]

    if path.lower().endswith(".gz"):
        return None
    with fits.open(path, memmap=True) as hdul:
        hdu = hdul[hdu_index]
        if not isinstance(hdu, fits.BinTableHDU) or hdu.header.get("PCOUNT", 0):
            return None
        row_bytes, n_total = hdu.header["NAXIS1"], hdu.header["NAXIS2"]
        dtype = hdu.columns.dtype.newbyteorder(">")
        if dtype.itemsize != row_bytes:
            return None
        offset = hdu.fileinfo()["datLoc"]
        columns = {c.name: c for c in hdu.columns}
    n = n_total if nrows is None else min(nrows, n_total)
    chunk_rows = max(1, (64 << 20) // row_bytes)  # ~64 MB per read
    parts: Dict[str, list] = {name: [] for name in names}
    with open(path, "rb") as f:
        f.seek(offset)
        done = 0
        while done < n:
            count = min(chunk_rows, n - done)
            rec = np.frombuffer(f.read(count * row_bytes), dtype=dtype, count=count)
            for name in names:
                parts[name].append(_decode_fits_column(rec[name], columns[name]))
            done += count
    return pd.DataFrame(
        {name: np.concatenate(chunks) if chunks else np.array([]) for name, chunks in parts.items()}
    )


def read_columns(
    path: str, names: List[str], hdu: Optional[int] = None, nrows: Optional[int] = None
) -> pd.DataFrame:
    """Read only ``names`` from a catalog file (the first ``nrows`` rows if given)."""
    fmt = file_format(path)
    if fmt == "fits":
        from astropy.io import fits  # type: ignore[import]

        hdu_index = hdu if hdu is not None else 1
        df = _read_fits_rows(path, hdu_index, names, nrows)
        if df is not None:
            return df
        with fits.open(path, memmap=True) as hdul:
            data = hdul[hdu_index].data
            if nrows is not None:
                data = data[:nrows]
            return pd.DataFrame({n: _native(data[n]) for n in names})
    if fmt == "parquet":
        import pyarrow.parquet as pq  # type: ignore[import]

        if nrows is None:
            return pq.read_table(path, columns=names).to_pandas()
        batch = next(pq.ParquetFile(path).iter_batches(batch_size=nrows, columns=names), None)
        return batch.to_pandas() if batch is not None else pd.DataFrame(columns=names)
    if fmt == "ecsv":
        from astropy.table import Table  # type: ignore[import]

        table = Table.read(path, format="ascii.ecsv")[names]
        if nrows is not None:
            table = table[:nrows]
        return table.to_pandas()
    if fmt == "csv":
        return pd.read_csv(path, usecols=names, nrows=nrows)[names]
    raise ValueError(f"unsupported file type: {path}")


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def compatible_columns(table: TableInfo, role: str) -> List[str]:
    """Columns whose type can fill ``role`` (dropdown options)."""
    kinds = ROLES_BY_NAME[role].kinds
    return [c.name for c in table.columns if c.kind in kinds]


def suggest_mapping(table: TableInfo) -> Dict[str, str]:
    """Prefill: {role: column} from common column names, each column used once."""
    by_lower = {c.name.lower(): c for c in table.columns}
    mapping: Dict[str, str] = {}
    used = set()
    for role in ROLES:
        for alias in role.aliases:
            col = by_lower.get(alias)
            if col is not None and col.kind in role.kinds and col.name not in used:
                mapping[role.name] = col.name
                used.add(col.name)
                break
    return mapping


def suggest_select_column(table: TableInfo) -> Optional[str]:
    by_lower = {c.name.lower(): c for c in table.columns if c.kind == BOOL}
    return next((by_lower[a].name for a in SELECT_ALIASES if a in by_lower), None)


def validate_mapping(spec: CatalogSpec, table: Optional[TableInfo] = None) -> ValidationResult:
    """Check a mapping against the file: names, types, then RA/Dec values on a row sample."""
    result = ValidationResult()
    if table is None:
        try:
            table = find_table(inspect_columns(spec.path), spec.hdu)
        except ValueError as e:
            result.errors.append(str(e))
            return result

    if not spec.name.strip():
        result.errors.append("Give the catalog a name.")
    for role in ROLES:
        if role.required and not spec.columns.get(role.name):
            result.errors.append(f"{role.label}: choose a column (required).")

    for role_name, col_name in spec.columns.items():
        role = ROLES_BY_NAME[role_name]
        col = table.column(col_name)
        if col is None:
            result.errors.append(f"{role.label}: no column '{col_name}' in the file.")
        elif col.kind not in role.kinds:
            result.errors.append(
                f"{role.label}: '{col_name}' is {col.kind}, expected {' or '.join(role.kinds)}."
            )
    if spec.columns.get("RA") and spec.columns.get("RA") == spec.columns.get("DEC"):
        result.errors.append("RA and Dec use the same column.")

    if spec.select_column:
        col = table.column(spec.select_column)
        if col is None:
            result.errors.append(f"Row selection: no column '{spec.select_column}' in the file.")
        elif col.kind != BOOL:
            result.errors.append(
                f"Row selection: '{spec.select_column}' is {col.kind}, expected bool."
            )
    for name in spec.hover_columns:
        col = table.column(name)
        if col is None:
            result.errors.append(f"Hover: no column '{name}' in the file.")
        elif col.kind == ARRAY:
            result.errors.append(f"Hover: '{name}' holds arrays and cannot be shown.")
    if result.errors:
        return result

    try:
        sample = read_columns(
            spec.path, [spec.columns["RA"], spec.columns["DEC"]], spec.hdu, nrows=SAMPLE_ROWS
        )
    except Exception as e:
        result.errors.append(f"Could not read the file: {e}")
        return result

    ra = pd.to_numeric(sample[spec.columns["RA"]], errors="coerce").to_numpy(dtype=float)
    dec = pd.to_numeric(sample[spec.columns["DEC"]], errors="coerce").to_numpy(dtype=float)
    ra, dec = ra[np.isfinite(ra)], dec[np.isfinite(dec)]
    if len(ra) == 0 or len(dec) == 0:
        result.errors.append("RA/Dec: no finite values in the first rows.")
        return result
    if ra.min() < 0 or ra.max() > 360:
        result.errors.append(
            f"RA: values {ra.min():.3f}..{ra.max():.3f} are outside 0..360 degrees."
        )
    elif ra.max() <= 24 and len(ra) > 10:
        result.warnings.append(
            f"RA: all values are within 0..24 ({ra.min():.3f}..{ra.max():.3f}); hours instead of degrees?"
        )
    if dec.min() < -90 or dec.max() > 90:
        result.errors.append(
            f"Dec: values {dec.min():.3f}..{dec.max():.3f} are outside -90..90 degrees."
        )

    n = f"{table.nrows:,} rows" if table.nrows is not None else "row count known after loading"
    result.info.append(
        f"{n}; first {len(sample):,}: RA {ra.min():.3f}..{ra.max():.3f}, Dec {dec.min():.3f}..{dec.max():.3f}"
    )
    return result


# ---------------------------------------------------------------------------
# Loaded catalog
# ---------------------------------------------------------------------------


def default_cache_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".cache", "clusterviz_catalogs")


class GalaxyCatalog:
    """A catalog's mapped columns in memory, under the standard role names.

    Role columns are named after the role (RA, DEC, SPEC_Z, ...); hover columns
    keep their file names (suffixed " (column)" if that clashes with a role name).
    Loading is lazy: call load(), or use any accessor.
    """

    def __init__(self, spec: CatalogSpec, cache_dir: Optional[str] = None):
        self.spec = spec
        self.cache_dir = cache_dir if cache_dir is not None else default_cache_dir()
        self.df: Optional[pd.DataFrame] = None
        self.n_total: Optional[int] = None  # rows in the file, before selection
        self.status = "not loaded"
        self._index = None

    # -- loading -------------------------------------------------------------

    def _cache_path(self) -> Optional[str]:
        """Parquet copy of the mapped columns, keyed by the file's identity and the mapping.

        A FITS table is stored row by row, so even one column means reading the
        whole file; the cache makes that a one-off per file version and mapping.
        """
        try:
            st = os.stat(self.spec.path)
        except OSError:
            return None
        key = json.dumps(
            [
                os.path.realpath(self.spec.path),
                st.st_size,
                st.st_mtime_ns,
                self.spec.hdu,
                self.spec.columns,
                self.spec.select_column,
                self.spec.hover_columns,
            ],
            sort_keys=True,
        )
        return os.path.join(
            self.cache_dir, hashlib.sha1(key.encode()).hexdigest()[:20] + ".parquet"
        )

    def load(self) -> bool:
        """Load (or reload) the catalog; False with ``status`` set on failure."""
        spec = self.spec
        self.df, self._index = None, None
        if not os.path.isfile(spec.path):
            self.status = f"file not found: {spec.path}"
            logger.warning(f"Catalog '{spec.name}': {self.status}")
            return False

        cache_path = self._cache_path()
        df = None
        if cache_path and os.path.isfile(cache_path):
            try:
                df = pd.read_parquet(cache_path)
            except Exception as e:
                logger.debug(f"Catalog '{spec.name}': ignoring unreadable cache {cache_path}: {e}")

        if df is None:
            try:
                df = self._standardize(read_columns(spec.path, spec.used_columns(), spec.hdu))
            except Exception as e:
                self.status = f"could not read {spec.path}: {e}"
                logger.warning(f"Catalog '{spec.name}': {self.status}")
                return False
            if cache_path:
                try:
                    os.makedirs(self.cache_dir, exist_ok=True)
                    tmp = f"{cache_path}.{os.getpid()}.tmp"
                    df.to_parquet(tmp, index=False)
                    os.replace(tmp, cache_path)
                except Exception as e:
                    logger.debug(f"Catalog '{spec.name}': could not write cache {cache_path}: {e}")

        self.n_total = int(df.attrs.get("n_total", len(df)))
        self.df = df.reset_index(drop=True)
        self.status = self._describe()
        logger.info(f"Catalog '{spec.name}': {self.status} ({spec.path})")
        return True

    @staticmethod
    def hover_name(column: str) -> str:
        """DataFrame column holding hover column ``column``."""
        return f"{column} (column)" if column in ROLES_BY_NAME else column

    def _standardize(self, raw: pd.DataFrame) -> pd.DataFrame:
        spec = self.spec
        keep = np.ones(len(raw), dtype=bool)
        if spec.select_column:
            keep &= raw[spec.select_column].to_numpy(dtype=bool)
        out = pd.DataFrame(index=raw.index)
        for role in ROLE_NAMES:
            if role in spec.columns:
                values = raw[spec.columns[role]]
                if ROLES_BY_NAME[role].kinds == NUMERIC:
                    values = pd.to_numeric(values, errors="coerce").astype(float)
                out[role] = values
        for col in spec.hover_columns:
            out[self.hover_name(col)] = raw[col]
        keep &= np.isfinite(out["RA"].to_numpy()) & np.isfinite(out["DEC"].to_numpy())
        out = out[keep]
        # Parquet keeps DataFrame.attrs, so the cached copy remembers the file's row count
        out.attrs["n_total"] = len(raw)
        return out

    def _describe(self) -> str:
        df = self.df
        text = f"{len(df):,} galaxies"
        if self.n_total is not None and self.n_total != len(df):
            text += f" of {self.n_total:,}"
            if self.spec.select_column:
                text += f" (where {self.spec.select_column})"
        if "CLUSTER_ID" in df.columns:
            text += f", {df['CLUSTER_ID'].nunique():,} clusters"
        return text

    def _ensure_loaded(self) -> bool:
        return self.df is not None or self.load()

    # -- access --------------------------------------------------------------

    def is_available(self) -> bool:
        return self._ensure_loaded()

    def capabilities(self) -> set:
        """Features this catalog's mapping enables (from the spec; no loading)."""
        mapped = set(self.spec.columns)
        caps = {"display", "match_position"}
        if "OBJECT_ID" in mapped:
            caps.add("match_id")
        if "SPEC_Z" in mapped:
            caps.add("specz")
        if "CLUSTER_ID" in mapped:
            caps.add("cluster_filter")
        return caps

    def get_all(self) -> Optional[pd.DataFrame]:
        return self.df if self._ensure_loaded() else None

    def cluster_ids(self) -> np.ndarray:
        """Unique merged-cluster IDs the catalog's galaxies belong to (empty if unmapped)."""
        df = self.get_all()
        if df is None or "CLUSTER_ID" not in df.columns:
            return np.array([], dtype=np.int64)
        return df["CLUSTER_ID"].dropna().unique()

    @property
    def index(self):
        """SpatialIndex over the catalog's positions, built on first use."""
        if self._index is None and self._ensure_loaded():
            from cluster_visualization.utils.spatial_index import SpatialIndex

            self._index = SpatialIndex(self.df["RA"].to_numpy(), self.df["DEC"].to_numpy())
        return self._index

    def in_box(self, ra_min: float, ra_max: float, dec_min: float, dec_max: float) -> pd.DataFrame:
        """Rows inside an RA/Dec box (empty frame if unavailable)."""
        df = self.get_all()
        if df is None:
            return pd.DataFrame()
        ra, dec = df["RA"].to_numpy(), df["DEC"].to_numpy()
        return df[(ra >= ra_min) & (ra <= ra_max) & (dec >= dec_min) & (dec <= dec_max)]
