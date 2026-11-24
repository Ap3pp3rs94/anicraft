#!/usr/bin/env python3
"""Run the synthetic nightly packaging suites together; no app build or signing.

`nightly-release-tests.py` (the dormant callers' and policy's contract tests) is not part of this
list: it arrives with the caller PR, which carries `nightly.yml`, `nightly-sign.yml` and
`nightly-signing-policy.json` (see docs/nightly-builds.md › Callers and policy).
"""
import importlib.util
from pathlib import Path
import unittest


def main() -> int:
    here = Path(__file__).resolve().parent
    suite = unittest.TestSuite()
    for name, relative in (
        ("anicraft_archive_suite", "nightly-archive-tests.py"),
        ("anicraft_plist_suite", "macos/nightly_plist_tests.py"),
        ("anicraft_mac_sign_suite", "macos/nightly_sign_tests.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, here / relative)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
