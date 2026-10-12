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


if __name__ == "__main__":
    unittest.main()
