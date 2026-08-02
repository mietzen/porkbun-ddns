import logging
import unittest
from unittest.mock import MagicMock, patch

from porkbun_ddns import cli
from porkbun_ddns.helpers import parse_log_level
from porkbun_ddns.test.test_porkbun_ddns import valid_config

logger = logging.getLogger("porkbun_ddns")


class TestParseLogLevel(unittest.TestCase):

    def test_valid_levels_case_insensitive(self):
        cases = {
            "DEBUG": logging.DEBUG,
            "debug": logging.DEBUG,
            "DeBuG": logging.DEBUG,
            "INFO": logging.INFO,
            "info": logging.INFO,
            "WARNING": logging.WARNING,
            "warning": logging.WARNING,
            "WARN": logging.WARNING,
            "warn": logging.WARNING,
            "ERROR": logging.ERROR,
            "error": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
            "critical": logging.CRITICAL,
        }
        for level, expected in cases.items():
            with self.subTest(level=level):
                self.assertEqual(parse_log_level(level), expected)

    def test_none_and_empty_default_to_info(self):
        self.assertEqual(parse_log_level(None), logging.INFO)
        self.assertEqual(parse_log_level(""), logging.INFO)

    def test_invalid_level_logs_warning_and_falls_back_to_info(self):
        with self.assertLogs("porkbun_ddns", level="WARNING") as captured:
            result = parse_log_level("not_a_level")
        self.assertEqual(result, logging.INFO)
        self.assertIn("not_a_level", captured.output[0])

    def test_invalid_level_falls_back_to_custom_default(self):
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            result = parse_log_level("bogus", default=logging.DEBUG)
        self.assertEqual(result, logging.DEBUG)


class TestCliLogLevel(unittest.TestCase):

    def tearDown(self):
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.INFO)

    @staticmethod
    def _patch_run():
        # keep cli.main hermetic: no config-file writes, no network
        return patch.multiple(
            "porkbun_ddns.cli",
            extract_config=MagicMock(return_value=valid_config),
            create_default_config_file=MagicMock(),
            PorkbunDDNS=MagicMock(),
        )

    def test_log_level_warning_sets_logger(self):
        with self._patch_run():
            cli.main(["example.com", "--log-level", "WARNING"])
        self.assertEqual(logger.level, logging.WARNING)

    def test_log_level_wins_over_verbose(self):
        with self._patch_run():
            cli.main(["example.com", "--log-level", "WARNING", "--verbose"])
        self.assertEqual(logger.level, logging.WARNING)

    def test_verbose_without_log_level_sets_debug(self):
        with self._patch_run():
            cli.main(["example.com", "--verbose"])
        self.assertEqual(logger.level, logging.DEBUG)

    def test_no_log_level_or_verbose_keeps_info(self):
        with self._patch_run():
            cli.main(["example.com"])
        self.assertEqual(logger.level, logging.INFO)


if __name__ == "__main__":
    unittest.main()
