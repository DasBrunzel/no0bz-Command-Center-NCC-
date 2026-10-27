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

