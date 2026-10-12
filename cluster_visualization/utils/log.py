"""Terminal logging for the app: one loguru sink on stdout.

Modules log with ``from loguru import logger``. ``setup_logging`` (called once by
cluster_dash_app.py after argument parsing) sets the format and the level:
``--log-level`` > ``CLUSTERVIZ_LOG_LEVEL`` > INFO. Records from the standard
``logging`` module (dash, werkzeug, astropy, ...) go to the same sink.

The sink is stdout, like the startup banner and SSH box that stay plain prints:
with output redirected to a file, one stream keeps the lines in order. Lines are
written with ``tqdm.write`` so they appear above any progress bar
(``tile_progress``) instead of breaking it.
"""

import inspect
import logging
import os
import sys

from loguru import logger

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
ENV_VAR = "CLUSTERVIZ_LOG_LEVEL"
FORMAT = (
    "<green>{time:HH:mm:ss}</green> <level>{level: <7}</level> "
    "<cyan>{name}</cyan> | <level>{message}</level>"
)
# Package prefixes left out of the module name shown in each line
_PREFIXES = ("cluster_visualization.src.", "cluster_visualization.")


def short_name(name: str) -> str:
    """Module name as shown: no package prefix, "app" for the entry script."""
    if name == "__main__":
        return "app"
    for prefix in _PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _patch(record) -> None:
    record["name"] = short_name(record["name"] or "")


# Libraries whose DEBUG output is noise even at --log-level DEBUG
_QUIET = ("PIL", "urllib3", "asyncio", "fsspec", "numexpr", "matplotlib")


class InterceptHandler(logging.Handler):
    """Send standard-library logging records to loguru (loguru's documented recipe)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # Report the caller of logging.*, not this handler
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def resolve_level(level=None) -> str:
    """Argument, else CLUSTERVIZ_LOG_LEVEL, else INFO; unknown names fall back to INFO."""
    name = str(level or os.environ.get(ENV_VAR) or "INFO").upper()
    return name if name in LEVELS else "INFO"


def _write(message) -> None:
    from tqdm import tqdm

    tqdm.write(str(message), end="")


def tile_progress(items, desc: str):
    """Progress bar over MER tiles being loaded (stderr, cleared when done).

    Shown only on a terminal and for more than one tile; otherwise the items are
    iterated as they are. Log lines keep their place above the bar (see ``_write``).
    """
    from tqdm import tqdm

    items = list(items)
    return tqdm(
        items,
        desc=desc,
        unit="tile",
        leave=False,
        dynamic_ncols=True,
        disable=len(items) < 2 or not sys.stderr.isatty(),
    )


def setup_logging(level=None) -> str:
    """Replace loguru's handlers with one stdout sink at the resolved level. Idempotent."""
    level = resolve_level(level)
    # Background-callback workers are separate processes that import loguru afresh: its
    # default handler reads the LOGURU_* variables, so they log the same way
    os.environ.update({
        ENV_VAR: level,
        "LOGURU_LEVEL": level,
        "LOGURU_FORMAT": FORMAT,
        "LOGURU_BACKTRACE": "NO",
        "LOGURU_DIAGNOSE": "NO",
    })
    logger.remove()
    logger.configure(patcher=_patch)
    logger.add(
        _write,
        level=level,
        colorize=sys.stdout.isatty(),
        format=FORMAT,
        backtrace=False,
        diagnose=False,  # tracebacks without local variables (DataFrames can be huge)
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.getLevelName(level), force=True)
    for name in _QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)
    return level
