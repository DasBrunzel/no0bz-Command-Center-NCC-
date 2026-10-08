from __future__ import annotations

from ncc.collectors.registry import ProviderRegistry, merge_metrics
from ncc.collectors.system import (
    DemoProvider,
    PsutilProvider,
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


def test_rate_pair_converts_and_smooths_network_counters() -> None:
    first = PsutilProvider._rate_pair((2_000_000, 1_000_000), (1_000_000, 500_000), 1.0, (0.0, 0.0))
    assert first == (3.6, 1.8)
    second = PsutilProvider._rate_pair((2_000_000, 1_000_000), (2_000_000, 1_000_000), 1.0, first)
    assert second == (1.98, 0.99)


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

