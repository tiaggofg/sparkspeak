"""Smoke test for package bootstrap."""

import sparkspeak


def test_package_imports() -> None:
    assert sparkspeak.__version__ == "0.1.0"
