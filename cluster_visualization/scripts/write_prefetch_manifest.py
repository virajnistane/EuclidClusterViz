"""Write the list of files the app imports, for the launcher's background prefetch.

On a cold cluster node every import reads its file from network storage (Ceph venv,
/pbs/home stdlib) one at a time. run_dash_app_venv.sh reads the files listed here in
parallel while the app starts, so Python finds them in the page cache.

The list holds exactly what Python loads: the app entry module is executed without
starting the server (main() only runs as __main__), then the modules the app imports
later on demand. Paths are in import order and point at the .pyc (or extension .so)
that Python actually reads, followed by the shared libraries those extensions load
(numpy.libs, scipy.libs, libarrow, ...), taken from /proc/self/maps.

Usage: python write_prefetch_manifest.py <project_dir> <output_file>
Run by setup_venv.sh after each sync and by "setup_venv.sh --manifest".
"""

import contextlib
import importlib
import importlib.util
import io
import os
import runpy
import sys

# Imported by the app only on first use (Globe view, HEALPix masks, CATRED, Parquet cache)
LAZY_MODULES = (
    "healpy",
    "scipy.spatial",
    "scipy.ndimage",
    "pyarrow.parquet",
    "astropy.wcs",
    "shapely.geometry",
    "PIL.Image",
)


def import_app(project_dir: str) -> None:
    """Run the app's module-level imports without starting the server."""
    app = os.path.join(project_dir, "cluster_visualization", "src", "cluster_dash_app.py")
    # As in cluster_dash_app.py: dash would otherwise pull in IPython/ipykernel
    sys.modules.setdefault("IPython", None)
    argv = sys.argv
    sys.argv = [app]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(app, run_name="clusterviz_manifest")
    except BaseException as exc:  # SystemExit from argparse/env checks included
        print(f"  Warning: app modules not fully imported ({type(exc).__name__}: {exc}); "
              "manifest is partial")
    finally:
        sys.argv = argv

    for name in LAZY_MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:
            print(f"  Warning: could not import {name} ({exc})")


def mapped_libraries() -> list:
    """Shared libraries mapped into this process (Linux), in address order."""
    paths = []
    try:
        with open("/proc/self/maps") as fh:
            for line in fh:
                parts = line.split(maxsplit=5)
                if len(parts) == 6 and ".so" in parts[5]:
                    paths.append(parts[5].strip())
    except OSError:
        pass
    return paths


def loaded_files(roots, first=()) -> list:
    """Files behind the loaded modules, in import order, then the shared libraries
    they pulled in; only files under the given roots. ``first`` are listed up front."""
    files, seen = [], {os.path.abspath(__file__)}  # never this script
    candidates = list(first)
    for name, module in list(sys.modules.items()):
        spec = getattr(module, "__spec__", None)
        # This script, and stdlib modules frozen into the interpreter (never read from disk)
        if name == "__main__" or getattr(spec, "origin", None) == "frozen":
            continue
        path = getattr(module, "__file__", None)
        if path:
            candidates.append(path)
    candidates += mapped_libraries()

    for path in candidates:
        path = os.path.abspath(path)
        if path.endswith(".py"):
            try:
                cached = importlib.util.cache_from_source(path)
            except (NotImplementedError, ValueError):
                cached = None
            if cached and os.path.isfile(cached):
                path = cached
        if path in seen or not path.startswith(roots) or not os.path.isfile(path):
            continue
        seen.add(path)
        files.append(path)
    return files


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    project_dir, output = os.path.abspath(sys.argv[1]), sys.argv[2]

    import_app(project_dir)
    # Venv (site-packages), the interpreter's stdlib and the project's own modules
    roots = tuple(os.path.abspath(p) + os.sep for p in (sys.prefix, sys.base_prefix, project_dir))
    # runpy drops the app's temporary module afterwards, so list its file explicitly
    app = os.path.join(project_dir, "cluster_visualization", "src", "cluster_dash_app.py")
    files = loaded_files(roots, first=[app])

    tmp = f"{output}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(files) + "\n")
    os.replace(tmp, output)

    size_mb = sum(os.path.getsize(f) for f in files) / 1e6
    print(f"Prefetch manifest: {len(files)} files, {size_mb:.1f} MB -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
