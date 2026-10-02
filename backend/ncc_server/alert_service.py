from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.config import ServerSettings
from ncc_server.models import AlertPolicy, AlertState, Node, TelemetryPoint, utc_now
from ncc_server.node_service import is_online


@dataclass(frozen=True)
class AlertNotification:
    alert_id: str
    state: str
    message: str


def evaluate_alerts(session: Session, settings: ServerSettings) -> list[AlertNotification]:
    notifications: list[AlertNotification] = []
    policy = get_alert_policy(session)
    nodes = session.scalars(select(Node)).all()
    for node in nodes:
        latest = session.scalar(
            select(TelemetryPoint)
            .where(TelemetryPoint.node_id == node.id)
            .order_by(TelemetryPoint.recorded_at.desc())
            .limit(1)
        )
        metrics = latest.payload if latest is not None else {}
        active = _active_alerts(node, metrics, settings, policy)
        states = {
            state.kind: state
            for state in session.scalars(select(AlertState).where(AlertState.node_id == node.id))
        }
        for kind, severity, message in active:
            state = states.pop(kind, None)
            if state is None:
                state = AlertState(node_id=node.id, kind=kind, severity=severity, message=message)
                session.add(state)
                session.flush()
            else:
                state.active = True
                state.severity = severity
                state.message = message
                state.resolved_at = None
                state.updated_at = utc_now()
            if settings.telegram_enabled and state.last_notified_state != "active":
                notifications.append(AlertNotification(state.id, "active", message))
        for state in states.values():
            if not state.active:
                continue
            state.active = False
            state.updated_at = utc_now()
            state.resolved_at = state.updated_at
            if state.last_notified_state == "active":
                notifications.append(
                    AlertNotification(state.id, "resolved", f"Entwarnung: {state.message}")
                )
    session.commit()
    return notifications


def mark_notified(session: Session, alert_id: str, state: str) -> None:
    alert = session.get(AlertState, alert_id)
    if alert is None:
        return
    alert.last_notified_state = state
    session.commit()


def get_alert_policy(session: Session) -> AlertPolicy:
    policy = session.get(AlertPolicy, "default")
    if policy is None:
        policy = AlertPolicy(id="default")
        session.add(policy)
        session.commit()
    return policy


def update_alert_policy(session: Session, values: dict[str, int]) -> AlertPolicy:
    policy = get_alert_policy(session)
    for name, value in values.items():
        setattr(policy, name, value)
    policy.updated_at = utc_now()
    session.commit()
    return policy


def _active_alerts(
    node: Node, metrics: dict[str, object], settings: ServerSettings, policy: AlertPolicy
) -> list[tuple[str, str, str]]:
    name = node.display_name
    alerts: list[tuple[str, str, str]] = []
    if not is_online(node, settings.node_offline_after_seconds):
        return [("offline", "critical", f"{name} ist offline.")]
    cpu = _number(_nested(metrics, "cpu", "percent"))
    memory = _number(_nested(metrics, "memory", "percent"))
    gpu = _number(_nested(metrics, "gpus", 0, "percent"))
    disks = metrics.get("disks")
    disk = max((_number(item.get("percent")) for item in disks if isinstance(item, dict)), default=0.0) if isinstance(disks, list) else 0.0
    for kind, label, value, threshold in (("cpu", "CPU", cpu, policy.cpu_threshold), ("memory", "RAM", memory, policy.memory_threshold), ("gpu", "GPU", gpu, policy.gpu_threshold), ("disk", "Laufwerk", disk, policy.disk_threshold)):
        if value >= threshold:
            severity = "critical" if value >= min(100, threshold + 5) else "warning"
            alerts.append((kind, severity, f"{name}: {label}-Auslastung bei {value:.0f} % ({severity})."))
    _unraid_alerts(node, metrics, alerts)
    return alerts


def _unraid_alerts(
    node: Node, metrics: dict[str, object], alerts: list[tuple[str, str, str]]
) -> None:
    """Add actionable Unraid-only warnings without waking sleeping disks."""
    if node.metadata_json.get("source") != "unraid-api":
        return
    name = node.display_name
    unraid = _dict(metrics.get("unraid"))
    array_state = str(unraid.get("array_state") or "").upper()
    if array_state and array_state not in {"STARTED", "STARTING"}:
        alerts.append(("unraid-array", "critical", f"{name}: Unraid-Array ist {array_state}."))
    cpu_temperature = _number(_nested(metrics, "cpu", "temperature_c"))
    if cpu_temperature >= 85:
        severity = "critical" if cpu_temperature >= 90 else "warning"
        alerts.append(("cpu-temperature", severity, f"{name}: CPU-Temperatur bei {cpu_temperature:.0f} °C ({severity})."))
    disks = metrics.get("disks")
    if isinstance(disks, list):
        for disk in disks:
            if not isinstance(disk, dict):
                continue
            temperature = _number(disk.get("temperature_c"))
            if temperature < 50:
                continue
            severity = "critical" if temperature >= 55 else "warning"
            label = str(disk.get("name") or disk.get("mount") or "Laufwerk")
            alerts.append((f"disk-temperature-{label.casefold()}", severity, f"{name}: {label} bei {temperature:.0f} °C ({severity})."))
    _workload_alerts(name, metrics.get("vms"), "vm", {"CRASHED", "ERROR", "FAILED"}, alerts)
    _workload_alerts(name, metrics.get("containers"), "container", {"DEAD", "RESTARTING", "ERROR"}, alerts)


def _workload_alerts(
    node_name: str, workloads: object, kind: str, unhealthy: set[str], alerts: list[tuple[str, str, str]]
) -> None:
    if not isinstance(workloads, list):
        return
    for workload in workloads:
        if not isinstance(workload, dict):
            continue
        state = str(workload.get("state") or "").upper()
        if state not in unhealthy:
            continue
        name = str(workload.get("name") or kind)
        alerts.append((f"{kind}-{name.casefold()}", "critical", f"{node_name}: {kind.upper()} „{name}“ meldet {state}."))


def _nested(value: dict[str, object], *path: str | int) -> object:
    current: object = value
    for part in path:
        if isinstance(part, str) and isinstance(current, dict):
            current = current.get(part)
        elif isinstance(part, int) and isinstance(current, list) and part < len(current):
            current = current[part]
        else:
            return None
    return current


def _number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
