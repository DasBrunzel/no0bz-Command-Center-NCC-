"""Pick the hardware readings NCC keeps in statistics from a telemetry point."""

from __future__ import annotations

from collections.abc import Mapping

# Readings in display order; the dashboard names them.
HARDWARE_METRICS = (
    "cpu_percent", "cpu_temperature_c", "cpu_power_w", "cpu_fan_rpm",
    "gpu_percent", "gpu_temperature_c", "gpu_hotspot_c", "gpu_power_w",
    "memory_percent", "ram_temperature_c", "drive_temperature_c", "case_fan_rpm",
)


def hardware_values(metrics: Mapping[str, object], sensor_labels: Mapping[str, object] | None = None) -> dict[str, float]:
    """Return positive readings; fans count only once the user gave them a role."""
    cpu = _mapping(metrics.get("cpu"))
    memory = _mapping(metrics.get("memory"))
    gpu = _first(metrics.get("gpus"))
    lhm_gpu = _first(metrics.get("lhm_gpus"))
    hardware = _mapping(metrics.get("hardware"))
    candidates: dict[str, object] = {
        "cpu_percent": cpu.get("percent"),
        "cpu_temperature_c": cpu.get("temperature_c"),
        "cpu_power_w": cpu.get("power_w"),
        "gpu_percent": gpu.get("percent"),
        # LibreHardwareMonitor has the more precise GPU sensors where present.
        "gpu_temperature_c": _number(lhm_gpu.get("temperature_c")) or gpu.get("temperature_c"),
        "gpu_hotspot_c": lhm_gpu.get("hotspot_temperature_c"),
        "gpu_power_w": _number(lhm_gpu.get("power_w")) or gpu.get("power_w"),
        "memory_percent": memory.get("percent"),
        "ram_temperature_c": _highest(hardware.get("memory_modules"), "temperature_c"),
        "drive_temperature_c": _highest(hardware.get("storage"), "temperature_c"),
    }
    board = _mapping(hardware.get("board"))
    fans = board.get("fans") if isinstance(board.get("fans"), list) else []
    for role, name in (("cpu", "cpu_fan_rpm"), ("case", "case_fan_rpm")):
        candidates[name] = _fan_with_role(fans, sensor_labels or {}, role)  # type: ignore[arg-type]
    return {
        name: float(value) for name, value in candidates.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    }


def system_power_w(values: Mapping[str, float]) -> float | None:
    """CPU plus GPU power; the rest of the PC has no sensor."""
    parts = [values[name] for name in ("cpu_power_w", "gpu_power_w") if name in values]
    return sum(parts) if parts else None


def _fan_with_role(fans: list[object], labels: Mapping[str, object], role: str) -> float | None:
    for fan in fans:
        if not isinstance(fan, dict):
            continue
        label = labels.get(f"fan:{fan.get('label')}")
        if isinstance(label, dict) and label.get("role") == role:
            return _number(fan.get("rpm"))
    return None


def _highest(items: object, key: str) -> float | None:
    values = [_number(item.get(key)) for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _first(value: object) -> Mapping[str, object]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}
