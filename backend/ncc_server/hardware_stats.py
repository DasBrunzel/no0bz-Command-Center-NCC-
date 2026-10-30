"""Hourly hardware statistics: temperatures, load, fans and energy per node.

Telemetry points are added to an hourly row as they arrive. Points stored
before this feature existed are added by a background backfill that walks
back through each node's history, so trends cover the past as well.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.database import Database
from ncc_server.hardware_metrics import HARDWARE_METRICS, hardware_values, system_power_w
from ncc_server.models import HardwareHourly, Node, TelemetryPoint, utc_now

# A longer gap means the device was off or offline, not drawing power.
MAX_ENERGY_GAP = timedelta(seconds=60)
BACKFILL_BATCH = 2000


def record_hardware_point(session: Session, node: Node, recorded_at: datetime, metrics: dict[str, object]) -> None:
    recorded_at = _aware(recorded_at)
    if node.rollup_live_since is None:
        node.rollup_live_since = recorded_at
    # Buffered points from before live tracking began belong to the backfill.
    if recorded_at < _aware(node.rollup_live_since):
        return
    _add_point(session, node, recorded_at, metrics)


def backfill_step(session: Session, node: Node, batch: int = BACKFILL_BATCH) -> int:
    """Add one batch of older telemetry for a node; return how many points."""
    if node.rollup_backfill_done:
        return 0
    if node.rollup_live_since is None:
        node.rollup_live_since = utc_now()
    before = _aware(node.rollup_backfilled_before or node.rollup_live_since)
    points = session.scalars(
        select(TelemetryPoint)
        .where(TelemetryPoint.node_id == node.id, TelemetryPoint.recorded_at < before)
        .order_by(TelemetryPoint.recorded_at.desc())
        .limit(batch)
    ).all()
    for point in points:
        _add_point(session, node, _aware(point.recorded_at), point.payload)
    if points:
        node.rollup_backfilled_before = _aware(points[-1].recorded_at)
    if len(points) < batch:
        node.rollup_backfill_done = True
    session.commit()
    return len(points)


def backfill_hardware_rollups(database: Database) -> int:
    with database.session() as session:
        node_ids = list(session.scalars(select(Node.id).where(Node.rollup_backfill_done.is_(False))).all())
    total = 0
    for node_id in node_ids:
        with database.session() as session:
            node = session.get(Node, node_id)
            if node is not None:
                total += backfill_step(session, node)
    return total


def hardware_statistics(
    session: Session, *, days: int, node_id: str | None, utc_offset_minutes: int, now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    query = select(HardwareHourly)
    if days:
        query = query.where(HardwareHourly.hour >= current - timedelta(days=days))
    if node_id:
        query = query.where(HardwareHourly.node_id == node_id)
    rows = session.scalars(query.order_by(HardwareHourly.hour)).all()
    names = {node.id: node.display_name for node in session.scalars(select(Node)).all()}
    offset = timedelta(minutes=utc_offset_minutes)
    daily: dict[str, dict[str, list[float]]] = defaultdict(dict)
    daily_energy: dict[str, float] = defaultdict(float)
    overall: dict[str, list[float]] = {}
    records: dict[str, dict[str, Any]] = {}
    energy = 0.0
    for row in rows:
        local = _aware(row.hour) + offset
        day = local.date().isoformat()
        daily_energy[day] += row.energy_wh
        energy += row.energy_wh
        for name, (value_sum, count, peak) in (row.values or {}).items():
            for target in (daily[day], overall):
                aggregate = target.setdefault(name, [0.0, 0.0, peak])
                aggregate[0] += value_sum
                aggregate[1] += count
                aggregate[2] = max(aggregate[2], peak)
            if name not in records or peak > records[name]["value"]:
                records[name] = {"value": round(peak, 1), "at": _aware(row.hour), "node_name": names.get(row.node_id)}
    return {
        "days": days,
        "metrics": [name for name in HARDWARE_METRICS if name in overall],
        "summary": {name: _summary(value) for name, value in overall.items()},
        "records": records,
        "energy_wh": round(energy, 1),
        "daily": [
            {"date": day, "energy_wh": round(daily_energy[day], 1), "metrics": {name: _summary(value) for name, value in values.items()}}
            for day, values in sorted(daily.items())
        ],
        "hours_covered": len(rows),
    }


def _add_point(session: Session, node: Node, recorded_at: datetime, metrics: dict[str, object]) -> None:
    hour = recorded_at.replace(minute=0, second=0, microsecond=0)
    row = session.scalar(select(HardwareHourly).where(HardwareHourly.node_id == node.id, HardwareHourly.hour == hour))
    if row is None:
        row = HardwareHourly(node_id=node.id, hour=hour, sample_count=0, values={}, energy_wh=0.0)
        session.add(row)
    readings = hardware_values(metrics, node.sensor_labels)
    values = dict(row.values or {})
    for name, value in readings.items():
        value_sum, count, peak = values.get(name, [0.0, 0.0, value])
        values[name] = [round(value_sum + value, 3), count + 1, max(peak, value)]
    row.values = values
    row.sample_count += 1
    power = system_power_w(readings)
    gap = _gap(row, recorded_at)
    if power is not None and gap is not None:
        row.energy_wh = round(row.energy_wh + power * gap.total_seconds() / 3600, 4)
    if row.first_point_at is None or recorded_at < _aware(row.first_point_at):
        row.first_point_at = recorded_at
    if row.last_point_at is None or recorded_at > _aware(row.last_point_at):
        row.last_point_at = recorded_at
    session.flush()


def _gap(row: HardwareHourly, recorded_at: datetime) -> timedelta | None:
    """Time since the neighbouring point, so each interval counts once."""
    if row.last_point_at is not None and recorded_at > _aware(row.last_point_at):
        gap = recorded_at - _aware(row.last_point_at)
    elif row.first_point_at is not None and recorded_at < _aware(row.first_point_at):
        # The backfill walks backwards through time.
        gap = _aware(row.first_point_at) - recorded_at
    else:
        return None
    return gap if gap <= MAX_ENERGY_GAP else None


def _summary(value: list[float]) -> dict[str, float]:
    value_sum, count, peak = value
    return {"average": round(value_sum / count, 1) if count else 0.0, "max": round(peak, 1)}


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
