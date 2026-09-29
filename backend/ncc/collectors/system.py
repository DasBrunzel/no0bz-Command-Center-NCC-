from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import psutil

from ncc.collectors.base import Capabilities, SensorProvider

MIB = 1024 * 1024


class PsutilProvider(SensorProvider):
    name = "psutil"
    priority = 50

    def is_available(self) -> bool:
        return True

    def probe(self) -> Capabilities:
        return Capabilities(self.name, True, ["cpu", "memory", "swap", "disk", "network", "battery", "processes"])

    def collect(self) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        net = psutil.net_io_counters()
        disks = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (PermissionError, OSError):
                continue
            disks.append({"name": partition.device, "mount": partition.mountpoint, "percent": usage.percent, "used_gb": round(usage.used / 1024**3, 2), "total_gb": round(usage.total / 1024**3, 2)})
        battery = psutil.sensors_battery()
        processes: list[dict[str, Any]] = []
        for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = process.info
                processes.append({"pid": info["pid"], "name": info["name"] or "unknown", "cpu": round(float(info["cpu_percent"] or 0), 1), "memory": round(float(info["memory_percent"] or 0), 1)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda item: item["cpu"] + item["memory"], reverse=True)
        return {
            "cpu": {"percent": psutil.cpu_percent(percpu=False), "per_core": psutil.cpu_percent(percpu=True), "frequency_mhz": _frequency(), "physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(logical=True), "model": platform.processor() or platform.machine()},
            "memory": {"percent": memory.percent, "used_gb": round(memory.used / 1024**3, 2), "available_gb": round(memory.available / 1024**3, 2), "total_gb": round(memory.total / 1024**3, 2)},
            "swap": {"percent": swap.percent, "used_gb": round(swap.used / 1024**3, 2), "total_gb": round(swap.total / 1024**3, 2)},
            "disks": disks,
            "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "errors": net.errin + net.errout, "drops": net.dropin + net.dropout},
            "battery": None if battery is None else {"percent": battery.percent, "plugged": battery.power_plugged, "seconds_left": battery.secsleft},
            "processes": processes[:30],
            "system": {"hostname": socket.gethostname(), "platform": platform.platform(), "boot_time": psutil.boot_time()},
        }


def _frequency() -> float | None:
    value = psutil.cpu_freq()
    return round(value.current, 1) if value else None


class NvidiaProvider(SensorProvider):
    name = "nvidia-nvml"
    priority = 90

    def is_available(self) -> bool:
        try:
            import pynvml  # type: ignore[import-not-found,unused-ignore]

            pynvml.nvmlInit()
            return bool(pynvml.nvmlDeviceGetCount() > 0)
        except Exception:
            return False

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["gpu"] if available else [], None if available else "NVML/NVIDIA GPU nicht verfügbar", "Optional nvidia-ml-py installieren")

    def collect(self) -> dict[str, Any]:
        import pynvml  # type: ignore[import-not-found,unused-ignore]

        gpus = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpus.append({"index": index, "name": pynvml.nvmlDeviceGetName(handle), "percent": utilization.gpu, "vram_percent": round(memory.used / memory.total * 100, 1), "temperature_c": pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)})
        return {"gpus": gpus}


class SmartctlProvider(SensorProvider):
    name = "smartctl"
    priority = 60
    interval = 60.0

    def is_available(self) -> bool:
        return shutil.which("smartctl") is not None

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["disk_health"] if available else [], None if available else "smartctl nicht gefunden", "smartmontools installieren")

    def collect(self) -> dict[str, Any]:
        result = subprocess.run(["smartctl", "--scan-open", "--json"], capture_output=True, text=True, timeout=8, shell=False, check=False)
        return {"disk_health": {"available": result.returncode in {0, 2}, "raw": result.stdout[:2000]}}


class LinuxHwmonProvider(SensorProvider):
    name = "linux-hwmon"
    platforms = {"linux"}
    priority = 70

    def is_available(self) -> bool:
        return platform.system() == "Linux" and Path("/sys/class/hwmon").is_dir()

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["temperatures", "fans", "gpu", "power"] if available else [], None if available else "Linux hwmon nicht verfügbar")

    def collect(self) -> dict[str, Any]:
        temperatures = []
        for path in Path("/sys/class/hwmon").glob("hwmon*/temp*_input"):
            try:
                temperatures.append({"sensor": str(path), "celsius": round(float(path.read_text().strip()) / 1000, 1)})
            except (OSError, ValueError):
                continue
        return {"temperatures": temperatures}


def parse_lhm_tree(
    node: dict[str, Any], output: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    values = output if output is not None else []
    raw_value = node.get("Value")
    if raw_value not in {None, "", "-"}:
        text = str(raw_value).replace(",", ".")
        number = "".join(char for char in text if char.isdigit() or char in ".-")
        try:
            value: float | str = float(number)
        except ValueError:
            value = text
        values.append({"name": str(node.get("Text", "sensor")), "value": value, "raw": text})
    for child in node.get("Children", []) or []:
        if isinstance(child, dict):
            parse_lhm_tree(child, values)
    return values


class LibreHardwareMonitorProvider(SensorProvider):
    name = "librehardwaremonitor"
    platforms = {"windows"}
    priority = 80

    def __init__(self, url: str) -> None:
        self.url = url

    def is_available(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            with urllib.request.urlopen(self.url, timeout=1) as response:
                return bool(response.status == 200)
        except (OSError, ValueError):
            return False

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(
            self.name,
            available,
            ["temperatures", "fans", "voltages", "power", "gpu"] if available else [],
            None if available else "LibreHardwareMonitor-Webserver nicht erreichbar",
            "Als Administrator starten und Remote Web Server auf Port 8085 aktivieren",
        )

    def collect(self) -> dict[str, Any]:
        with urllib.request.urlopen(self.url, timeout=3) as response:
            tree = json.loads(response.read().decode("utf-8"))
        return {"lhm_sensors": parse_lhm_tree(tree), "lhm_source": self.name}


class DemoProvider(SensorProvider):
    name = "demo"
    priority = 100

    def __init__(self) -> None:
        self._tick = 0

    def is_available(self) -> bool:
        return True

    def probe(self) -> Capabilities:
        return Capabilities(self.name, True, ["cpu", "memory", "network", "gpu", "fans", "disk"])

    def collect(self) -> dict[str, Any]:
        self._tick += 1
        wave = self._tick % 40
        return {"cpu": {"percent": 25 + wave, "temperature_c": 52 + wave / 4}, "memory": {"percent": 48 + wave / 5, "used_gb": 15.4, "total_gb": 32}, "network": {"download_mbps": 30 + wave * 1.5, "upload_mbps": 4 + wave / 3}, "gpus": [{"index": 0, "name": "Demo GPU", "percent": 35 + wave, "vram_percent": 42, "temperature_c": 61}], "fans": [{"name": "CPU", "rpm": 980 + wave * 12}], "disks": [{"name": "Demo NVMe", "percent": 62, "temperature_c": 39}]}

