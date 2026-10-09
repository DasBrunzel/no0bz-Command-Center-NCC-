"""Versioned NCC 0.6 telemetry payload."""

import os


# The Core supplies the exact signed manifest version to its child process.
# Keeping a static fallback preserves direct/local development runs, while a
# staged payload now confirms the version that Core actually verified.
__version__ = (
    os.environ.get("NCC_PAYLOAD_VERSION", "").strip()
    or os.environ.get("NCC_TEST_PAYLOAD_VERSION", "").strip()
    or "0.6.0-beta.1"
)
