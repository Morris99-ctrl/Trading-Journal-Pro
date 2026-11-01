"""Run the legacy assertion suite through unittest discovery."""

import unittest

from test_suite import run_tests


class LegacySuiteTests(unittest.TestCase):
    def test_legacy_suite(self):
        run_tests()


if __name__ == "__main__":
    unittest.main()
