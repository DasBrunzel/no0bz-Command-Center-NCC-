from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path

from ncc_service.environment import load_environment_file


def child_python_executable() -> str:
    """Return python.exe when the current process is hosted by pythonservice.exe."""
    executable = Path(sys.executable)
    if executable.name.lower() != "pythonservice.exe":
        return sys.executable
    candidates = (
        Path(sys.prefix) / "Scripts" / "python.exe",
        executable.parent / "Scripts" / "python.exe",
        executable.with_name("python.exe"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"Python interpreter not found next to service host: {executable}")


class ManagedProcess:
    def __init__(self, module: str, config_path: Path, log_path: Path) -> None:
        self.module = module
        self.config_path = config_path
        self.log_path = log_path
        self.stop_event = threading.Event()
        self.process: subprocess.Popen[bytes] | None = None

    def run(self) -> int:
        environment = load_environment_file(self.config_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self.log_path.open("ab", buffering=0) as output:
            self.process = subprocess.Popen(  # noqa: S603 - fixed interpreter and module
                [child_python_executable(), "-m", self.module],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                env=environment,
                creationflags=creation_flags,
            )
            while not self.stop_event.wait(0.5):
                code = self.process.poll()
                if code is not None:
                    logging.error("NCC child process exited with code %d", code)
                    return code
            self._terminate()
            return 0

    def stop(self) -> None:
        self.stop_event.set()
        self._terminate()

    def _terminate(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
