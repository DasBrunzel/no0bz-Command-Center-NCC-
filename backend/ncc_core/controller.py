from __future__ import annotations

import shutil
from pathlib import Path

from ncc_core.manifest import ReleaseArtifact, verify_artifact
from ncc_core.state import CoreState


class CoreController:
    """Safe reference for staging and rolling back 0.6 payload archives.

    It deliberately never starts a service or reads NCC credentials. The future
    compiled Core implements this same state transition contract.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.payloads_dir = root / "payloads"
        self.state_path = root / "state" / "core-state.json"

    def state(self) -> CoreState:
        return CoreState.load(self.state_path)

    def stage(self, artifact_file: Path, artifact: ReleaseArtifact) -> Path:
        verify_artifact(artifact_file, artifact)
        destination_dir = self.payloads_dir / artifact.payload_version
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / "payload.archive"
        temporary = destination.with_suffix(".tmp")
        shutil.copyfile(artifact_file, temporary)
        verify_artifact(temporary, artifact)
        temporary.replace(destination)
        return destination

    def activate(self, version: str) -> CoreState:
        if not (self.payloads_dir / version / "payload.archive").is_file():
            raise ValueError("payload is not staged")
        current = self.state()
        state = CoreState(
            active_payload=version,
            previous_payload=current.active_payload if current.active_payload != version else current.previous_payload,
            last_update=CoreState.now(),
            health="awaiting_health",
        )
        state.save(self.state_path)
        return state

    def report_health(self, version: str, healthy: bool) -> CoreState:
        current = self.state()
        if current.active_payload != version:
            raise ValueError("health report is not for the active payload")
        if healthy:
            state = CoreState(version, current.previous_payload, current.last_update, "healthy")
        elif current.previous_payload:
            state = CoreState(current.previous_payload, version, CoreState.now(), "rolled_back")
        else:
            state = CoreState(None, version, CoreState.now(), "rolled_back")
        state.save(self.state_path)
        return state
