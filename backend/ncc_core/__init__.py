"""NCC 0.6 Core reference semantics.

This package is deliberately not wired into NCC 0.5 services.  It specifies and
tests the persistent staging, activation and rollback behaviour that the compiled
NCC Core will implement for Windows and Linux.
"""

from ncc_core.controller import CoreController
from ncc_core.manifest import ReleaseArtifact, ReleaseManifest, load_manifest
from ncc_core.state import CoreState

__all__ = ["CoreController", "CoreState", "ReleaseArtifact", "ReleaseManifest", "load_manifest"]
