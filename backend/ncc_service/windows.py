from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import servicemanager  # type: ignore[import-untyped]
    import win32event  # type: ignore[import-untyped]
    import win32service  # type: ignore[import-untyped]
    import win32serviceutil  # type: ignore[import-untyped]
else:
    servicemanager = win32event = win32service = win32serviceutil = None

from ncc_service.process import ManagedExecutable, ManagedProcess


def service_root() -> Path:
    return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "no0bz" / "NCC"


if sys.platform == "win32":

    class _BaseNccService(win32serviceutil.ServiceFramework):  # type: ignore[misc]
        _module = ""
        _config_name = ""
        _log_name = ""

        def __init__(self, args: list[str]) -> None:
            super().__init__(args)
            self._stop_handle = win32event.CreateEvent(None, 0, 0, None)
            root = service_root()
            self._managed = ManagedProcess(
                self._module,
                root / "config" / self._config_name,
                root / "logs" / self._log_name,
            )

        def SvcStop(self) -> None:  # noqa: N802 - Windows SCM contract
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._managed.stop()
            win32event.SetEvent(self._stop_handle)

        def SvcDoRun(self) -> None:  # noqa: N802 - Windows SCM contract
            servicemanager.LogInfoMsg(f"{self._svc_display_name_} starting")
            try:
                # A Windows Server can otherwise keep the service in START_PENDING
                # until the child process is ready.  A slow protected-process
                # initialization then triggers the SCM's 30 second timeout even
                # though the NCC worker itself is healthy.
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                code = self._managed.run()
            except Exception:
                logging.exception("NCC service failed")
                servicemanager.LogErrorMsg(f"{self._svc_display_name_} failed; see log file")
                raise
            if code:
                servicemanager.LogErrorMsg(
                    f"{self._svc_display_name_} child exited with code {code}"
                )
            else:
                servicemanager.LogInfoMsg(f"{self._svc_display_name_} stopped")


    class AgentWindowsService(_BaseNccService):
        _svc_name_ = "NccAgent"
        _svc_display_name_ = "no0bz Command Center Agent"
        _svc_description_ = "Collects local telemetry and sends it to the NCC server."
        _module = "ncc_agent.main"
        _config_name = "agent.env"
        _log_name = "agent.log"


    class ServerWindowsService(_BaseNccService):
        _svc_name_ = "NccServer"
        _svc_display_name_ = "no0bz Command Center Server"
        _svc_description_ = "Hosts the NCC API, fleet dashboard, and telemetry store."
        _module = "ncc_server.main"
        _config_name = "server.env"
        _log_name = "server.log"

    class CoreWindowsService(_BaseNccService):
        _svc_name_ = "NccCore"
        _svc_display_name_ = "no0bz Command Center Core"
        _svc_description_ = "Starts and supervises the versioned NCC telemetry payload."
        _module = ""
        _config_name = "core.env"
        _log_name = "core.log"

        def __init__(self, args: list[str]) -> None:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_handle = win32event.CreateEvent(None, 0, 0, None)
            root = service_root()
            self._managed = ManagedExecutable(
                root / "core" / "ncc-core.exe", ["service"],
                root / "config" / self._config_name, root / "logs" / self._log_name,
            )

else:
    AgentWindowsService: Any = None
    ServerWindowsService: Any = None
    CoreWindowsService: Any = None


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if sys.platform != "win32":
        raise SystemExit("NCC Windows services can only be managed on Windows")
    if not arguments or arguments[0] not in {"agent", "server", "core"}:
        raise SystemExit(
            "usage: python -m ncc_service.windows {agent|server|core} "
            "[install|update|remove|start|stop|restart|debug]"
        )
    component = arguments.pop(0)
    service_class: Any = {"agent": AgentWindowsService, "server": ServerWindowsService, "core": CoreWindowsService}[component]
    win32serviceutil.HandleCommandLine(
        service_class,
        serviceClassString=f"ncc_service.windows.{service_class.__name__}",
        argv=[sys.argv[0], *arguments],
    )


if __name__ == "__main__":
    main()
