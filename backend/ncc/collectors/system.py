from __future__ import annotations

import json
import platform
import re
import shutil
import socket
import subprocess
import time
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

import psutil

from ncc.collectors.base import Capabilities, SensorProvider

MIB = 1024 * 1024


@lru_cache(maxsize=1)
def cpu_model_name() -> str:
    """Return the marketing name instead of Windows' Family/Model identifier."""
    if platform.system() == "Windows":
        try:
            import winreg

            with winreg.OpenKey(  # type: ignore[attr-defined,unused-ignore]
                winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined,unused-ignore]
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, _ = winreg.QueryValueEx(  # type: ignore[attr-defined,unused-ignore]
                    key, "ProcessorNameString"
                )
                if str(value).strip():
                    return str(value).strip()
        except (ImportError, OSError):
            pass
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.lower().startswith(("model name", "hardware")):
                    return line.partition(":")[2].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def _drive_key(device: str) -> str:
    return device.rstrip("\\/").split("\\")[-1].lower()


def normalize_process_cpu(percent: float, logical_cores: int) -> float:
    """Translate psutil's multi-core process usage to a 0–100 system scale."""
    return max(0.0, min(100.0, percent / max(1, logical_cores)))


class PsutilProvider(SensorProvider):
    name = "psutil"
    priority = 50

    def __init__(self) -> None:
        self._sample_time: float | None = None
        self._network: tuple[int, int] | None = None
        self._disk: dict[str, tuple[int, int]] = {}
        self._network_rate = (0.0, 0.0)
        self._disk_rates: dict[str, tuple[float, float]] = {}
        self._windows_disk_map: dict[str, str] | None = None

    def is_available(self) -> bool:
        return True

    def probe(self) -> Capabilities:
        return Capabilities(self.name, True, ["cpu", "memory", "swap", "disk", "network", "battery", "processes"])

    def collect(self) -> dict[str, Any]:
        now = time.monotonic()
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        net, interface = self._active_network_counters()
        disk_counters = psutil.disk_io_counters(perdisk=True) or {}
        elapsed = max(now - self._sample_time, 0.001) if self._sample_time is not None else 0.0
        download, upload = self._rate_pair(
            (net.bytes_recv, net.bytes_sent), self._network, elapsed, self._network_rate
        )
        self._network = (net.bytes_recv, net.bytes_sent)
        self._network_rate = (download, upload)
        disks = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (PermissionError, OSError):
                continue
            counter_key = self._counter_key(partition.device, partition.mountpoint, disk_counters)
            counter = disk_counters.get(counter_key) if counter_key else None
            read_rate = write_rate = 0.0
            if counter_key is not None and counter is not None:
                previous = self._disk.get(counter_key)
                old_rate = self._disk_rates.get(counter_key, (0.0, 0.0))
                read_rate, write_rate = self._rate_pair(
                    (counter.read_bytes, counter.write_bytes), previous, elapsed, old_rate, bits=False
                )
                self._disk[counter_key] = (counter.read_bytes, counter.write_bytes)
                self._disk_rates[counter_key] = (read_rate, write_rate)
            disks.append({"name": partition.device, "mount": partition.mountpoint, "filesystem": partition.fstype, "percent": usage.percent, "used_gb": round(usage.used / 1024**3, 2), "total_gb": round(usage.total / 1024**3, 2), "read_mbps": read_rate, "write_mbps": write_rate})
        self._sample_time = now
        battery = psutil.sensors_battery()
        processes: list[dict[str, Any]] = []
        logical_cores = max(1, psutil.cpu_count(logical=True) or 1)
        for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = process.info
                # psutil reports a process' use across all logical CPUs.  A process
                # can therefore exceed 100% on a multi-core machine; normalize it
                # to the same 0–100 scale used by the dashboard's system CPU gauge.
                process_cpu = normalize_process_cpu(float(info["cpu_percent"] or 0), logical_cores)
                processes.append({"pid": info["pid"], "name": info["name"] or "unknown", "cpu": round(process_cpu, 1), "memory": round(float(info["memory_percent"] or 0), 1)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda item: item["cpu"] + item["memory"], reverse=True)
        return {
            "cpu": {"percent": psutil.cpu_percent(percpu=False), "per_core": psutil.cpu_percent(percpu=True), "frequency_mhz": _frequency(), "physical_cores": psutil.cpu_count(logical=False), "logical_cores": logical_cores, "model": cpu_model_name()},
            "memory": {"percent": memory.percent, "used_gb": round(memory.used / 1024**3, 2), "available_gb": round(memory.available / 1024**3, 2), "total_gb": round(memory.total / 1024**3, 2)},
            "swap": {"percent": swap.percent, "used_gb": round(swap.used / 1024**3, 2), "total_gb": round(swap.total / 1024**3, 2)},
            "disks": disks,
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "total_sent_gb": round(net.bytes_sent / 1024**3, 2),
                "total_recv_gb": round(net.bytes_recv / 1024**3, 2),
                "download_mbps": download,
                "upload_mbps": upload,
                "interface": interface,
                "errors": net.errin + net.errout,
                "drops": net.dropin + net.dropout,
            },
            "battery": None if battery is None else {"percent": battery.percent, "plugged": battery.power_plugged, "seconds_left": battery.secsleft},
            "processes": processes[:30],
            "system": {"hostname": socket.gethostname(), "platform": platform.platform(), "boot_time": psutil.boot_time()},
        }

    def _active_network_counters(self) -> tuple[Any, str]:
        counters = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        active = [name for name, stat in stats.items() if stat.isup and not name.lower().startswith(("loopback", "lo")) and name in counters]
        if not active:
            return psutil.net_io_counters(), "Auto"
        best = max(active, key=lambda name: counters[name].bytes_recv + counters[name].bytes_sent)
        return counters[best], best

    @staticmethod
    def _rate_pair(current: tuple[int, int], previous: tuple[int, int] | None, elapsed: float, old: tuple[float, float], *, bits: bool = True) -> tuple[float, float]:
        if previous is None or elapsed <= 0:
            return 0.0, 0.0
        factor = 8 / 1_000_000 if bits else 1 / MIB
        raw = tuple(max(0.0, (current[i] - previous[i]) * factor / elapsed) for i in range(2))
        alpha = 0.45
        return round(alpha * raw[0] + (1 - alpha) * old[0], 2), round(alpha * raw[1] + (1 - alpha) * old[1], 2)

    def _counter_key(self, device: str, mount: str, counters: dict[str, Any]) -> str | None:
        keys = {key.lower(): key for key in counters}
        direct = _drive_key(device)
        if direct in keys:
            return keys[direct]
        if platform.system() == "Windows":
            mapping = self._windows_disk_mapping()
            drive = mount[:1].upper()
            physical = mapping.get(drive, "").lower()
            return keys.get(physical)
        base = re.sub(r"p?\d+$", "", direct)
        return keys.get(base)

    def _windows_disk_mapping(self) -> dict[str, str]:
        if self._windows_disk_map is not None:
            return self._windows_disk_map
        self._windows_disk_map = {}
        for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            number = _windows_volume_disk_number(drive)
            if number is not None:
                self._windows_disk_map[drive] = f"PhysicalDrive{number}"
        return self._windows_disk_map


def _windows_volume_disk_number(drive: str) -> int | None:
    """Map a drive letter to its physical disk without WMI/admin privileges."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DiskExtent(ctypes.Structure):
            _fields_ = [("disk_number", wintypes.DWORD), ("starting_offset", ctypes.c_longlong), ("extent_length", ctypes.c_longlong)]

        class VolumeExtents(ctypes.Structure):
            _fields_ = [("count", wintypes.DWORD), ("extent", DiskExtent)]

        kernel32 = ctypes.WinDLL(  # type: ignore[attr-defined,unused-ignore]
            "kernel32", use_last_error=True
        )
        handle = kernel32.CreateFileW(f"\\\\.\\{drive}:", 0, 3, None, 3, 0, None)
        if handle == wintypes.HANDLE(-1).value:
            return None
        try:
            output = VolumeExtents()
            returned = wintypes.DWORD()
            ok = kernel32.DeviceIoControl(handle, 0x560000, None, 0, ctypes.byref(output), ctypes.sizeof(output), ctypes.byref(returned), None)
            return int(output.extent.disk_number) if ok and output.count else None
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, ValueError):
        return None


def _frequency() -> float | None:
    value = psutil.cpu_freq()
    return round(value.current, 1) if value else None


class NvidiaProvider(SensorProvider):
    name = "nvidia-nvml"
    priority = 90

    def is_available(self) -> bool:
        try:
            import pynvml  # type: ignore[import-not-found,import-untyped,unused-ignore]

            pynvml.nvmlInit()
            return bool(pynvml.nvmlDeviceGetCount() > 0)
        except Exception:
            return False

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["gpu"] if available else [], None if available else "NVML/NVIDIA GPU nicht verfügbar", "Optional nvidia-ml-py installieren")

    def collect(self) -> dict[str, Any]:
        import pynvml  # type: ignore[import-not-found,import-untyped,unused-ignore]

        gpus = []
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            try:
                power_w = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
            except Exception:
                power_w = None
            try:
                fan_percent = pynvml.nvmlDeviceGetFanSpeed(handle)
            except Exception:
                fan_percent = None
            gpus.append(
                {
                    "index": index,
                    "name": name,
                    "percent": utilization.gpu,
                    "vram_percent": round(memory.used / memory.total * 100, 1),
                    "vram_used_gb": round(memory.used / 1024**3, 2),
                    "vram_total_gb": round(memory.total / 1024**3, 2),
                    "temperature_c": pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU),
                    "power_w": power_w,
                    "fan_percent": fan_percent,
                    "source": self.name,
                }
            )
        return {"gpus": gpus}


class WindowsGpuProvider(SensorProvider):
    """Vendor-neutral Windows GPU data using built-in WMI and performance counters."""

    name = "windows-gpu"
    platforms = {"windows"}
    priority = 75

    def __init__(self) -> None:
        self._adapters: list[dict[str, Any]] | None = None
        self._last_percent = 0.0

    def is_available(self) -> bool:
        return platform.system() == "Windows" and bool(self._adapter_info())

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["gpu"] if available else [], None if available else "Keine Windows-GPU gefunden", "Aktuellen AMD/Intel-Grafiktreiber installieren")

    def _adapter_info(self) -> list[dict[str, Any]]:
        if self._adapters is not None:
            return self._adapters
        self._adapters = []
        try:
            import winreg

            path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(  # type: ignore[attr-defined,unused-ignore]
                winreg.HKEY_LOCAL_MACHINE, path  # type: ignore[attr-defined,unused-ignore]
            ) as root:
                for index in range(
                    winreg.QueryInfoKey(root)[0]  # type: ignore[attr-defined,unused-ignore]
                ):
                    try:
                        with winreg.OpenKey(  # type: ignore[attr-defined,unused-ignore]
                            root,
                            winreg.EnumKey(  # type: ignore[attr-defined,unused-ignore]
                                root, index
                            ),
                        ) as key:
                            name = str(
                                winreg.QueryValueEx(  # type: ignore[attr-defined,unused-ignore]
                                    key, "DriverDesc"
                                )[0]
                            )
                            provider = str(
                                winreg.QueryValueEx(  # type: ignore[attr-defined,unused-ignore]
                                    key, "ProviderName"
                                )[0]
                            )
                            if any(word in name.lower() for word in ("virtual", "remote", "basic display")):
                                continue
                            self._adapters.append({"name": name, "provider": provider})
                    except OSError:
                        continue
        except (ImportError, OSError):
            pass
        return self._adapters

    def collect(self) -> dict[str, Any]:
        percent = self._gpu_percent()
        adapters = self._adapter_info()
        return {
            "gpus": [
                {
                    "index": index,
                    "name": item["name"],
                    "percent": percent,
                    "vram_percent": 0.0,
                    "vram_used_gb": None,
                    "vram_total_gb": None,
                    "temperature_c": None,
                    "power_w": None,
                    "source": self.name,
                }
                for index, item in enumerate(adapters)
            ],
            "process_gpu": self._process_gpu_percent(),
        }

    def _gpu_percent(self) -> float:
        try:
            command = "(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction Stop).CounterSamples | Select-Object InstanceName,CookedValue | ConvertTo-Json -Compress"
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=5, shell=False, check=False)
            rows = json.loads(result.stdout or "[]")
            if isinstance(rows, dict):
                rows = [rows]
            values = [float(row.get("CookedValue") or 0) for row in rows]
            raw = min(100.0, sum(value for value in values if value > 0))
            self._last_percent = round(raw * 0.5 + self._last_percent * 0.5, 1)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return self._last_percent

    def _process_gpu_percent(self) -> dict[str, float]:
        """Read Windows GPU Engine counters grouped by PID when available."""
        try:
            command = "(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction Stop).CounterSamples | Select-Object InstanceName,CookedValue | ConvertTo-Json -Compress"
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=5, shell=False, check=False)
            rows = json.loads(result.stdout or "[]")
            if isinstance(rows, dict):
                rows = [rows]
            usage: dict[str, float] = {}
            for row in rows:
                match = re.search(r"pid_(\\d+)", str(row.get("InstanceName") or ""), re.IGNORECASE)
                if match:
                    pid = match.group(1)
                    usage[pid] = min(100.0, usage.get(pid, 0.0) + max(0.0, float(row.get("CookedValue") or 0)))
            return {pid: round(value, 1) for pid, value in usage.items()}
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
            return {}


class LinuxAmdGpuProvider(SensorProvider):
    name = "linux-amdgpu"
    platforms = {"linux"}
    priority = 75

    def _cards(self) -> list[Path]:
        cards = []
        for card in Path("/sys/class/drm").glob("card[0-9]*"):
            try:
                if card.joinpath("device/vendor").read_text().strip().lower() == "0x1002":
                    cards.append(card)
            except OSError:
                continue
        return cards

    def is_available(self) -> bool:
        return platform.system() == "Linux" and bool(self._cards())

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["gpu"] if available else [], None if available else "Keine AMDGPU-sysfs-Geräte gefunden", "amdgpu-Kerneltreiber aktivieren")

    @staticmethod
    def _number(path: Path) -> float | None:
        try:
            return float(path.read_text().strip())
        except (OSError, ValueError):
            return None

    def collect(self) -> dict[str, Any]:
        gpus = []
        for index, card in enumerate(self._cards()):
            device = card / "device"
            used, total = self._number(device / "mem_info_vram_used"), self._number(device / "mem_info_vram_total")
            temperature = next(
                (
                    value
                    for path in device.glob("hwmon/hwmon*/temp1_input")
                    if (value := self._number(path)) is not None
                ),
                None,
            )
            power = next(
                (
                    value
                    for path in device.glob("hwmon/hwmon*/power1_average")
                    if (value := self._number(path)) is not None
                ),
                None,
            )
            fan = next(
                (
                    value
                    for path in device.glob("hwmon/hwmon*/fan1_input")
                    if (value := self._number(path)) is not None
                ),
                None,
            )
            name = "AMD Radeon GPU"
            try:
                slot = device.resolve().name
                result = subprocess.run(["lspci", "-s", slot], capture_output=True, text=True, timeout=2, shell=False, check=False)
                if result.stdout.strip():
                    name = result.stdout.partition(": ")[2].strip() or name
            except (OSError, subprocess.SubprocessError):
                pass
            gpus.append(
                {
                    "index": index,
                    "name": name,
                    "percent": self._number(device / "gpu_busy_percent") or 0.0,
                    "vram_percent": round(used / total * 100, 1) if used is not None and total else 0.0,
                    "vram_used_gb": round(used / 1024**3, 2) if used is not None else None,
                    "vram_total_gb": round(total / 1024**3, 2) if total is not None else None,
                    "temperature_c": round(temperature / 1000, 1) if temperature is not None else None,
                    "power_w": round(power / 1_000_000, 1) if power is not None else None,
                    "fan_rpm": round(fan) if fan is not None else None,
                    "source": self.name,
                }
            )
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
        temperatures: list[dict[str, Any]] = []
        fans: list[dict[str, Any]] = []
        powers: list[dict[str, Any]] = []
        cpu_temperature: float | None = None
        for directory in Path("/sys/class/hwmon").glob("hwmon*"):
            try:
                chip = directory.joinpath("name").read_text().strip()
            except OSError:
                chip = directory.name
            for path in directory.glob("temp*_input"):
                try:
                    sensor_id = path.name.removesuffix("_input")
                    label_path = directory / f"{sensor_id}_label"
                    label = label_path.read_text().strip() if label_path.exists() else sensor_id
                    celsius = round(float(path.read_text().strip()) / 1000, 1)
                    entry = {"chip": chip, "label": label, "celsius": celsius}
                    temperatures.append(entry)
                    if cpu_temperature is None and chip.lower() in {"coretemp", "k10temp", "zenpower", "peci_cputemp"}:
                        cpu_temperature = celsius
                except (OSError, ValueError):
                    continue
            for path in directory.glob("fan*_input"):
                try:
                    sensor_id = path.name.removesuffix("_input")
                    label_path = directory / f"{sensor_id}_label"
                    label = label_path.read_text().strip() if label_path.exists() else sensor_id
                    fans.append({"chip": chip, "label": label, "rpm": round(float(path.read_text().strip()))})
                except (OSError, ValueError):
                    continue
            for path in directory.glob("power*_average"):
                try:
                    sensor_id = path.name.removesuffix("_average")
                    label_path = directory / f"{sensor_id}_label"
                    label = label_path.read_text().strip() if label_path.exists() else sensor_id
                    powers.append({"chip": chip, "label": label, "watts": round(float(path.read_text().strip()) / 1_000_000, 1)})
                except (OSError, ValueError):
                    continue
        payload: dict[str, Any] = {"hardware": {"temperatures": temperatures, "fans": fans, "powers": powers}}
        if cpu_temperature is not None:
            payload["cpu"] = {"temperature_c": cpu_temperature}
        return payload


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

