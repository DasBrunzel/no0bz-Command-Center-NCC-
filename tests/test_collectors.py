from __future__ import annotations

from ncc.collectors.registry import ProviderRegistry
from ncc.collectors.system import DemoProvider, parse_lhm_tree
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

