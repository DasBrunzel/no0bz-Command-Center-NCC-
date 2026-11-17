"""GPS history of app nodes: intake from telemetry, heatmap cells, GPX export, deletion."""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ncc_server.models import LocationPoint, Node, utc_now
from ncc_server.schemas import LocationHeatmapResponse

# A fix worse than this is too vague for a heatmap (cell towers, cold starts).
MAX_ACCURACY_M = 250.0
# About 11 m at the equator; fine enough for streets, coarse enough to merge repeats.
CELL_DECIMALS = 4
MAX_CELLS = 20_000


def take_location(node: Node, metrics: dict[str, Any], recorded_at: datetime) -> LocationPoint | None:
    """Remove the GPS fix from a telemetry payload and return it as a location point.

    The fix is always removed, so it is never stored inside telemetry. It is
    only kept when the node's owner switched location tracking on.
    """
    raw = metrics.pop("location", None)
    android = metrics.get("android")
    if isinstance(android, dict):
        raw = android.pop("location", raw)
    if not node.location_tracking or not isinstance(raw, dict):
        return None
    latitude, longitude = _number(raw.get("lat")), _number(raw.get("lon"))
    accuracy = _number(raw.get("accuracy_m"))
    if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if accuracy is not None and (accuracy < 0 or accuracy > MAX_ACCURACY_M):
        return None
    return LocationPoint(node_id=node.id, recorded_at=recorded_at, latitude=latitude, longitude=longitude, accuracy_m=accuracy)


def location_heatmap(session: Session, node_id: str, days: int) -> LocationHeatmapResponse:
    since = utc_now() - timedelta(days=days)
    rows = session.execute(
        select(LocationPoint.latitude, LocationPoint.longitude)
        .where(LocationPoint.node_id == node_id, LocationPoint.recorded_at >= since)
    ).all()
    cells = Counter((round(lat, CELL_DECIMALS), round(lon, CELL_DECIMALS)) for lat, lon in rows)
    first, last = session.execute(
        select(func.min(LocationPoint.recorded_at), func.max(LocationPoint.recorded_at))
        .where(LocationPoint.node_id == node_id, LocationPoint.recorded_at >= since)
    ).one()
    total_all = session.scalar(select(func.count()).select_from(LocationPoint).where(LocationPoint.node_id == node_id)) or 0
    return LocationHeatmapResponse(
        days=days,
        points=len(rows),
        stored_points=total_all,
        first_at=first,
        last_at=last,
        cells=[[lat, lon, count] for (lat, lon), count in cells.most_common(MAX_CELLS)],
    )


def location_gpx(session: Session, node: Node, days: int) -> str:
    """The track of the last [days] days as GPX 1.1, one track segment per day."""
    since = utc_now() - timedelta(days=days)
    points = session.scalars(
        select(LocationPoint)
        .where(LocationPoint.node_id == node.id, LocationPoint.recorded_at >= since)
        .order_by(LocationPoint.recorded_at)
    ).all()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="no0bz Command Center" xmlns="http://www.topografix.com/GPX/1/1">',
        f"  <trk><name>{escape(node.display_name)}</name>",
    ]
    day = None
    for point in points:
        recorded = _as_utc(point.recorded_at)
        if recorded.date() != day:
            if day is not None:
                lines.append("    </trkseg>")
            lines.append("    <trkseg>")
            day = recorded.date()
        lines.append(
            f'      <trkpt lat="{point.latitude:.6f}" lon="{point.longitude:.6f}">'
            f"<time>{recorded.strftime('%Y-%m-%dT%H:%M:%SZ')}</time></trkpt>"
        )
    if day is not None:
        lines.append("    </trkseg>")
    lines += ["  </trk>", "</gpx>", ""]
    return "\n".join(lines)


def delete_locations(session: Session, node_id: str) -> int:
    result = session.execute(delete(LocationPoint).where(LocationPoint.node_id == node_id))
    session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def set_location_tracking(session: Session, node: Node, enabled: bool) -> None:
    node.location_tracking = enabled
    node.updated_at = utc_now()
    session.commit()


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
