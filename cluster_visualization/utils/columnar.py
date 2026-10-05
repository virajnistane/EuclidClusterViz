"""
Parquet storage for numpy structured arrays (catalog caches).

Columns are written one by one in native byte order, so a reader can load only
the columns it needs. The exact numpy dtype (field order, string widths, vector
shapes) and a small JSON ``meta`` dict travel in the Parquet schema metadata and
are restored on read.

pyarrow is optional: without it ``HAVE_ARROW`` is False and callers fall back to
pickle.
"""

import json
import os
import threading
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

try:
    import pyarrow as pa
    import pyarrow.parquet as pq

    HAVE_ARROW = True
except ImportError:  # pragma: no cover - depends on the environment
    pa = None
    pq = None
    HAVE_ARROW = False

_META_KEY = b"clusterviz"


def _native(col: np.ndarray) -> np.ndarray:
    """Return ``col`` as a plain ndarray in native byte order."""
    col = np.asarray(col)
    if not col.dtype.isnative:
        col = col.astype(col.dtype.newbyteorder("="))
    return col


def _to_arrow(col: np.ndarray):
    """Convert one numpy column to an Arrow array (vector columns as fixed-size lists)."""
    if col.dtype.kind == "O" or col.dtype.fields is not None:
        raise TypeError(f"unsupported column dtype {col.dtype}")
    if col.ndim == 1:
        return pa.array(col)
    width = int(np.prod(col.shape[1:]))
    flat = pa.array(np.ascontiguousarray(col).reshape(-1))
    return pa.FixedSizeListArray.from_arrays(flat, width)


def write_structured(path: str, arr: np.ndarray, meta: Optional[Dict[str, Any]] = None) -> None:
    """Write a structured array to ``path`` as Parquet (atomic).

    Raises TypeError for arrays Parquet cannot hold (no fields, object or
    variable-length columns); RuntimeError when pyarrow is missing.
    """
    if not HAVE_ARROW:
        raise RuntimeError("pyarrow is not installed")
    names = getattr(arr.dtype, "names", None)
    if not names:
        raise TypeError("not a structured array")

    columns, fields = [], []
    for name in names:
        # Field access (not a raw view) so FITS scaling and logical columns apply
        col = _native(arr[name])
        columns.append(_to_arrow(col))
        fields.append([name, col.dtype.str, list(col.shape[1:])])

    table = pa.Table.from_arrays(columns, names=list(names))
    payload = json.dumps({"fields": fields, "meta": meta or {}})
    table = table.replace_schema_metadata({_META_KEY: payload.encode()})

    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        pq.write_table(table, tmp, compression="zstd")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_structured(
    path: str, columns: Optional[Sequence[str]] = None
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Read a structured array written by ``write_structured``.

    ``columns`` limits the read to those fields (unknown names are ignored);
    the result keeps the stored field order.
    """
    if not HAVE_ARROW:
        raise RuntimeError("pyarrow is not installed")
    schema_meta = pq.read_schema(path).metadata or {}
    info = json.loads(schema_meta[_META_KEY].decode())
    fields = info["fields"]
    if columns is not None:
        wanted = set(columns)
        fields = [f for f in fields if f[0] in wanted]

    table = pq.read_table(path, columns=[f[0] for f in fields], memory_map=True)
    dtype = np.dtype([(name, np.dtype(code), tuple(shape)) for name, code, shape in fields])
    out = np.empty(table.num_rows, dtype=dtype)
    for name, _code, shape in fields:
        chunked = table.column(name)
        if shape:
            flat = chunked.combine_chunks().flatten().to_numpy(zero_copy_only=False)
            out[name] = flat.reshape((table.num_rows, *shape))
        else:
            out[name] = chunked.to_numpy()
    # Record dtype, as np.array(FITS_rec) gives: rows allow attribute access
    return out.view(np.dtype((np.record, out.dtype))), info.get("meta", {})
