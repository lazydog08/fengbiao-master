import unittest

from fengbiao.cli import _summary_exit_code


class CliTests(unittest.TestCase):
    def test_summary_exit_code_fails_on_total_or_partial_errors(self):
        self.assertEqual(_summary_exit_code({"creators_checked": 0, "errors": []}), 1)
        self.assertEqual(_summary_exit_code({"creators_checked": 2, "errors": [{"creator": "x"}]}), 1)
        self.assertEqual(_summary_exit_code({"creators_checked": 2, "errors": []}), 0)
