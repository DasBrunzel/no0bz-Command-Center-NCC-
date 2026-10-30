from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ncc.collectors.registry import ProviderRegistry, merge_metrics
from ncc.collectors.system import (
    DemoProvider,
    PsutilProvider,
    lhm_snapshot_metrics,
    normalize_process_cpu,
    parse_lhm_tree,
)
from ncc.config import Settings


def test_demo_provider_shape() -> None:
    metrics = DemoProvider().collect()
    assert 0 <= metrics["cpu"]["percent"] <= 100
    assert metrics["gpus"][0]["name"] == "Demo GPU"


def test_demo_registry_capabilities() -> None:
    registry = ProviderRegistry(Settings(token="test", demo=True))
    assert registry.capabilities[0].available
    assert "cpu" in registry.collect()


def test_parses_recursive_lhm_tree() -> None:
    tree = {"Text": "root", "Children": [{"Text": "CPU Package", "Value": "61.5 °C"}]}
    sensors = parse_lhm_tree(tree)
    assert sensors == [{"name": "CPU Package", "value": 61.5, "raw": "61.5 °C"}]


def test_lhm_helper_snapshot_maps_sensor_values_without_replacing_primary_gpu() -> None:
    metrics = lhm_snapshot_metrics([
        {"hardware_type": "Cpu", "hardware_name": "AMD Ryzen", "hardware_id": "/cpu/0", "type": "Temperature", "name": "CPU Package", "value": 62.4, "unit": "°C"},
        {"hardware_type": "Cpu", "hardware_name": "AMD Ryzen", "hardware_id": "/cpu/0", "type": "Power", "name": "Package", "value": 93.2, "unit": "W"},
        {"hardware_type": "GpuNvidia", "hardware_name": "NVIDIA RTX", "hardware_id": "/gpu/0", "type": "Temperature", "name": "GPU Core", "value": 57.0, "unit": "°C"},
        {"hardware_type": "GpuNvidia", "hardware_name": "NVIDIA RTX", "hardware_id": "/gpu/0", "type": "Fan", "name": "GPU Fan", "value": 1200, "unit": "RPM"},
    ])
    assert metrics["cpu"] == {"temperature_c": 62.4, "power_w": 93.2}
    assert metrics["lhm_gpus"][0]["fan_rpm"] == 1200
    assert "gpus" not in metrics
    assert metrics["hardware"]["provider"] == "librehardwaremonitor"


def test_rate_pair_converts_and_smooths_network_counters() -> None:
    first = PsutilProvider._rate_pair((2_000_000, 1_000_000), (1_000_000, 500_000), 1.0, (0.0, 0.0))
    assert first == (3.6, 1.8)
    second = PsutilProvider._rate_pair((2_000_000, 1_000_000), (2_000_000, 1_000_000), 1.0, first)
    assert second == (1.98, 0.99)


def test_network_interface_follows_current_traffic_not_old_cumulative_total(monkeypatch: Any) -> None:
    provider = PsutilProvider()
    counters = {
        "old": SimpleNamespace(bytes_recv=1_000_000_000, bytes_sent=100_000_000),
        "active": SimpleNamespace(bytes_recv=1000, bytes_sent=1000),
    }
    monkeypatch.setattr("ncc.collectors.system.psutil.net_if_stats", lambda: {
        "old": SimpleNamespace(isup=True), "active": SimpleNamespace(isup=True),
    })
    monkeypatch.setattr("ncc.collectors.system.psutil.net_io_counters", lambda pernic=True: counters)
    assert provider._active_network_counters()[1] == "old"
    provider._network_interface = "old"
    counters["active"] = SimpleNamespace(bytes_recv=101_000, bytes_sent=21_000)
    assert provider._active_network_counters()[1] == "active"


def test_rate_pair_converts_disk_bytes_to_mib() -> None:
    read, write = PsutilProvider._rate_pair((2 * 1024**2, 1024**2), (0, 0), 1.0, (0.0, 0.0), bits=False)
    assert read == 0.9
    assert write == 0.45


def test_process_cpu_is_normalized_to_system_percent() -> None:
    assert normalize_process_cpu(800.0, 8) == 100.0
    assert normalize_process_cpu(400.0, 8) == 50.0


def test_sensor_provider_extends_cpu_metrics_without_losing_psutil_data() -> None:
    metrics = {"cpu": {"percent": 42.0, "logical_cores": 16}}
    merge_metrics(metrics, {"cpu": {"temperature_c": 61.5}})
    assert metrics == {"cpu": {"percent": 42.0, "logical_cores": 16, "temperature_c": 61.5}}


class _IntermittentProvider:
    name = "intermittent-test"
    priority = 1

    def __init__(self) -> None:
        self.fail = False

    def is_available(self) -> bool:
        return True

    def collect(self) -> dict[str, Any]:
        if self.fail:
            raise TimeoutError("simulated busy sensor")
        return {"cpu": {"percent": 87.5}, "memory": {"percent": 64.0}}


def test_registry_keeps_recent_values_when_a_provider_times_out() -> None:
    registry = ProviderRegistry(Settings(token="test", demo=True))
    provider = _IntermittentProvider()
    registry.providers = [provider]  # type: ignore[assignment]

    assert registry.collect()["cpu"]["percent"] == 87.5
    provider.fail = True
    snapshot = registry.collect()

    assert snapshot["cpu"]["percent"] == 87.5
    assert snapshot["memory"]["percent"] == 64.0



def _sensor(hardware_type: str, hardware_name: str, hardware_id: str, kind: str, name: str, value: float) -> dict[str, Any]:
    return {"hardware_type": hardware_type, "hardware_name": hardware_name, "hardware_id": hardware_id, "type": kind, "name": name, "value": value, "unit": ""}


def test_lhm_snapshot_groups_drive_memory_and_board_sensors() -> None:
    metrics = lhm_snapshot_metrics([
        _sensor("Cpu", "AMD Ryzen 7 5700X", "/amdcpu/0", "Temperature", "Core (Tctl/Tdie)", 65.25),
        _sensor("Storage", "CT2000P3SSD8", "/nvme/3", "Temperature", "Temperature #1", 35.85),
        _sensor("Storage", "CT2000P3SSD8", "/nvme/3", "Temperature", "Composite Temperature", 36),
        _sensor("Storage", "CT2000P3SSD8", "/nvme/3", "Temperature", "Critical Temperature", 94),
        _sensor("Storage", "Samsung SSD 860 EVO 500GB ", "/ssd/0", "Temperature", "Temperature", 41),
        _sensor("Memory", "G Skill (#2)", "/memory/dimm/2", "Temperature", "DIMM #2", 38.75),
        _sensor("Memory", "G Skill (#2)", "/memory/dimm/2", "Temperature", "Thermal Sensor High Limit", 0),
        _sensor("SuperIO", "Nuvoton NCT6798D", "/lpc/nct6798d/0", "Fan", "Fan #1", 0),
        _sensor("SuperIO", "Nuvoton NCT6798D", "/lpc/nct6798d/0", "Fan", "Fan #2", 1137.32),
        _sensor("SuperIO", "Nuvoton NCT6798D", "/lpc/nct6798d/0", "Control", "Fan #2", 57.25),
        _sensor("SuperIO", "Nuvoton NCT6798D", "/lpc/nct6798d/0", "Temperature", "Temperature #1", 39),
        _sensor("GpuNvidia", "RTX 3060 Ti", "/gpu-nvidia/0", "Temperature", "GPU Core", 41),
    ])
    hardware = metrics["hardware"]
    assert metrics["cpu"]["temperature_c"] == 65.25
    assert hardware["storage"] == [
        {"name": "CT2000P3SSD8", "temperature_c": 36.0},
        {"name": "Samsung SSD 860 EVO 500GB", "temperature_c": 41.0},
    ]
    assert hardware["memory_modules"] == [{"name": "G Skill (#2)", "slot": "DIMM #2", "temperature_c": 38.75}]
    assert hardware["board"] == {
        "chip": "Nuvoton NCT6798D",
        "fans": [{"label": "Fan #2", "rpm": 1137, "control_percent": 57}],
        "temperatures": [{"label": "Temperature #1", "value": 39.0}],
    }
    assert all("Critical" not in entry["label"] for entry in hardware["temperatures"])
    # A GPU without its own hotspot or memory sensor must not repeat the core value.
    assert "memory_temperature_c" not in metrics["lhm_gpus"][0]
    assert "hotspot_temperature_c" not in metrics["lhm_gpus"][0]


FAKE_HELPER = """
import json, sys
count = 0
for line in sys.stdin:
    count += 1
    if count == 3:
        sys.exit(1)
    sensor = {"hardware_type": "Cpu", "hardware_name": "CPU", "hardware_id": "/cpu/0", "type": "Temperature", "name": "Package", "value": 50 + count, "unit": ""}
    print(json.dumps({"schema_version": 1, "sensors": [sensor]}), flush=True)
"""


def test_lhm_helper_stays_running_and_restarts_after_exit(tmp_path: Any, monkeypatch: Any) -> None:
    import sys

    import pytest
    from ncc.collectors import system

    script = tmp_path / "fake_helper.py"
    script.write_text(FAKE_HELPER, encoding="utf-8")
    provider = system.LibreHardwareMonitorProvider("http://127.0.0.1:1/data.json")
    monkeypatch.setattr(provider, "_helper_command", lambda: [sys.executable, "-I", str(script)])
    monkeypatch.setattr(system, "pawnio_status", lambda: "running")
    try:
        first = provider.collect()
        process = provider._process
        second = provider.collect()
        assert (first["cpu"]["temperature_c"], second["cpu"]["temperature_c"]) == (51, 52)
        assert provider._process is process
        assert first["hardware"]["pawnio"] == "running"
        with pytest.raises(RuntimeError):
            provider.collect()
        # The next sample starts a fresh helper.
        assert provider.collect()["cpu"]["temperature_c"] == 51
    finally:
        provider._stop_helper()
