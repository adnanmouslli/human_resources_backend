#!/usr/bin/env python
"""تشغيل اختبارات حد السلف:

    python tests/run_advance_limit_tests.py
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromName('tests.test_advance_limit_service'))
    suite.addTests(loader.loadTestsFromName('tests.test_advance_limit_routes'))
    suite.addTests(loader.loadTestsFromName('tests.test_shift_access_service'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(
        f"\nSummary: ran={result.testsRun} "
        f"failures={len(result.failures)} errors={len(result.errors)}"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
