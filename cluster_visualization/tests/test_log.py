"""Terminal logging setup (cluster_visualization/utils/log.py)."""

import io
import logging
import os
import sys
import unittest
from unittest import mock

from loguru import logger

from cluster_visualization.utils import log


class TestSetupLogging(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items()
               if k != log.ENV_VAR and not k.startswith("LOGURU_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.out = io.StringIO()
        stdout = mock.patch("sys.stdout", self.out)
        stdout.start()
        self.addCleanup(stdout.stop)

        # Give loguru and the root logger back as the other tests expect them
        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level

        def restore():
            logger.remove()
            logger.configure(patcher=None)
            logger.add(sys.stderr)
            root.handlers[:] = handlers
            root.setLevel(level)

        self.addCleanup(restore)

    def test_level_precedence(self):
        self.assertEqual(log.resolve_level(), "INFO")
        os.environ[log.ENV_VAR] = "warning"
        self.assertEqual(log.resolve_level(), "WARNING")
        self.assertEqual(log.resolve_level("debug"), "DEBUG")
        self.assertEqual(log.resolve_level("nonsense"), "INFO")

    def test_debug_hidden_at_info(self):
        log.setup_logging()
        logger.debug("hidden line")
        logger.info("shown line")
        text = self.out.getvalue()
        self.assertNotIn("hidden line", text)
        self.assertIn("shown line", text)
        self.assertIn("INFO", text)

    def test_idempotent_single_sink(self):
        log.setup_logging("INFO")
        log.setup_logging("INFO")
        logger.info("once")
        self.assertEqual(self.out.getvalue().count("once"), 1)

    def test_level_exported_for_workers(self):
        log.setup_logging("debug")
        self.assertEqual(os.environ[log.ENV_VAR], "DEBUG")
        self.assertEqual(os.environ["LOGURU_LEVEL"], "DEBUG")
        self.assertEqual(os.environ["LOGURU_DIAGNOSE"], "NO")

    def test_stdlib_logging_reaches_sink(self):
        log.setup_logging("INFO")
        logging.getLogger("some.library").warning("from stdlib")
        text = self.out.getvalue()
        self.assertIn("from stdlib", text)
        self.assertIn("WARNING", text)

    def test_exception_without_locals(self):
        log.setup_logging("INFO")
        local_value = "x" * 50  # shown in the traceback if diagnose were on
        try:
            raise ValueError(f"boom {len(local_value)}")
        except ValueError:
            logger.exception("failed")
        text = self.out.getvalue()
        self.assertIn("ValueError: boom 50", text)
        self.assertNotIn("x" * 50, text)

    def test_short_module_names(self):
        self.assertEqual(log.short_name("cluster_visualization.src.data.loader"), "data.loader")
        self.assertEqual(log.short_name("cluster_visualization.utils.disk_cache"), "utils.disk_cache")
        self.assertEqual(log.short_name("data.loader"), "data.loader")
        self.assertEqual(log.short_name("__main__"), "app")

    def test_tile_progress_hidden_without_terminal(self):
        err = io.StringIO()  # not a tty
        with mock.patch("sys.stderr", err):
            self.assertEqual(list(log.tile_progress([1, 2, 3], "tiles")), [1, 2, 3])
        self.assertEqual(err.getvalue(), "")

    def test_tile_progress_bar_and_logs_on_terminal(self):
        log.setup_logging("INFO")
        err = io.StringIO()
        err.isatty = lambda: True
        with mock.patch("sys.stderr", err):
            seen = []
            for tile in log.tile_progress([101, 102, 103], "CATRED MER tiles"):
                logger.info(f"loaded tile {tile}")
                seen.append(tile)
        self.assertEqual(seen, [101, 102, 103])
        self.assertIn("CATRED MER tiles", err.getvalue())
        self.assertIn("/3 [", err.getvalue())  # redrawn every 0.1 s, so not always at 3/3
        # Log lines stay whole on stdout, one per tile
        lines = [ln for ln in self.out.getvalue().splitlines() if "loaded tile" in ln]
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].endswith("loaded tile 101"), lines[0])

    def test_tile_progress_single_tile_no_bar(self):
        err = io.StringIO()
        err.isatty = lambda: True
        with mock.patch("sys.stderr", err):
            self.assertEqual(list(log.tile_progress([7], "tiles")), [7])
        self.assertEqual(err.getvalue(), "")

    def test_profiler_table_only_at_debug(self):
        from cluster_visualization.utils.profiler import TraceProfiler

        profiler = TraceProfiler(enabled=True)
        self.addCleanup(profiler.reset)  # stats are shared by all instances
        profiler.record("test:section", 0.01)
        log.setup_logging("INFO")
        profiler.print_stats(header="t")
        self.assertNotIn("test:section", self.out.getvalue())
        log.setup_logging("DEBUG")
        profiler.print_stats(header="t")
        self.assertIn("test:section", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
