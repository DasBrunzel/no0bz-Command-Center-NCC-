"""Game sessions, automatic gaming mode and playtime statistics.

Agents report the running game with every telemetry point. Sessions are built
from those points, so play that happened while the server was unreachable is
added once the agent's buffer arrives.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.hardware_metrics import hardware_values, system_power_w
from ncc_server.models import AuditEvent, Game, GameSession, Node, utc_now

# Points of the same game closer than this belong to one session. It also
# bridges loading screens and a quick restart of the game.
SESSION_GAP = timedelta(minutes=5)
# How long automatic gaming mode stays on after the last point with a game.
AUTO_GAMING_GRACE = timedelta(minutes=5)
# Buffered points from the past must not switch gaming mode on again.
AUTO_GAMING_RECENT = timedelta(minutes=2)
# A longer gap between two points is not counted as energy drawn.
ENERGY_GAP = timedelta(seconds=60)
# The now-playing card disappears once no point arrived for this long.
NOW_PLAYING_STALE = timedelta(seconds=90)
GAME_TRACKING_LEVELS = ("off", "presence", "titles")
LAUNCHERS = {"steam", "epic", "gog", "xbox", "battlenet"}


@dataclass(slots=True)
class ReportedGame:
    title: str | None
    launcher: str | None
    app_id: str | None


def prepare_game_metric(node: Node, metrics: dict[str, object]) -> ReportedGame | None:
    """Apply the node's privacy level to a point before it is stored."""
    raw = metrics.pop("game", None)
    if node.game_tracking == "off" or not isinstance(raw, dict):
        return None
    if node.game_tracking == "presence":
        metrics["game"] = {"active": True}
        return ReportedGame(None, None, None)
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    launcher = raw.get("launcher") if raw.get("launcher") in LAUNCHERS else "other"
    app_id = raw.get("app_id")
    app_id = str(app_id)[:64] if isinstance(app_id, (str, int)) and str(app_id) else None
    executable = raw.get("executable")
    metrics["game"] = {
        "title": title.strip()[:128],
        "launcher": launcher,
        "app_id": app_id,
        "executable": executable[:128] if isinstance(executable, str) else None,
    }
    return ReportedGame(title.strip()[:128], str(launcher), app_id)


def record_game_point(
    session: Session,
    node: Node,
    recorded_at: datetime,
    reported: ReportedGame,
    metrics: dict[str, object],
) -> None:
    recorded_at = _aware(recorded_at)
    game = _game_for(session, reported) if reported.title else None
    game_id = game.id if game else None
    latest = session.scalar(
        select(GameSession)
        .where(GameSession.node_id == node.id)
        .order_by(GameSession.ended_at.desc())
        .limit(1)
    )
    if (
        latest is not None
        and latest.game_id == game_id
        and recorded_at <= _aware(latest.ended_at) + SESSION_GAP
        and recorded_at >= _aware(latest.started_at) - SESSION_GAP
    ):
        current = latest
    else:
        current = GameSession(node_id=node.id, game_id=game_id, started_at=recorded_at, ended_at=recorded_at, sample_count=0, hardware={})
        session.add(current)
    previous_end = _aware(current.ended_at) if current.sample_count else None
    current.sample_count += 1
    hardware = dict(current.hardware or {})
    readings = hardware_values(metrics, node.sensor_labels)
    for name, value in readings.items():
        total, count, peak = hardware.get(name, [0.0, 0.0, value])
        hardware[name] = [round(total + value, 3), count + 1, max(peak, value)]
    power = system_power_w(readings)
    if power is not None and previous_end is not None and timedelta(0) < recorded_at - previous_end <= ENERGY_GAP:
        # Stored as [Wh, 0, 0] so it travels with the other readings.
        energy = hardware.get("energy_wh", [0.0, 0.0, 0.0])
        hardware["energy_wh"] = [round(energy[0] + power * (recorded_at - previous_end).total_seconds() / 3600, 4), 0.0, 0.0]
    current.hardware = hardware
    current.started_at = min(_aware(current.started_at), recorded_at)
    current.ended_at = max(_aware(current.ended_at), recorded_at)
    if node.auto_gaming_mode and recorded_at >= utc_now() - AUTO_GAMING_RECENT:
        until = recorded_at + AUTO_GAMING_GRACE
        if node.auto_gaming_until is None or _aware(node.auto_gaming_until) < until:
            node.auto_gaming_until = until
    session.flush()


def gaming_mode_active(node: Node, now: datetime | None = None) -> bool:
    current = now or utc_now()
    return any(value is not None and _aware(value) > current for value in (node.gaming_mode_until, node.auto_gaming_until))


def now_playing(session: Session, node: Node) -> dict[str, Any] | None:
    latest = session.scalar(
        select(GameSession)
        .where(GameSession.node_id == node.id, GameSession.ended_at >= utc_now() - NOW_PLAYING_STALE)
        .order_by(GameSession.ended_at.desc())
        .limit(1)
    )
    if latest is None:
        return None
    game = latest.game
    return {
        "session_id": latest.id,
        "game_id": game.id if game else None,
        "title": game.title if game else None,
        "launcher": game.launcher if game else None,
        "started_at": _aware(latest.started_at),
        "has_artwork": bool(game and game.header_content_type),
        "genres": list(game.genres or []) if game else [],
    }


def update_game_settings(session: Session, node_id: str, game_tracking: str, auto_gaming_mode: bool) -> Node | None:
    node = session.get(Node, node_id)
    if node is None:
        return None
    node.game_tracking = game_tracking
    node.auto_gaming_mode = auto_gaming_mode
    if not auto_gaming_mode or game_tracking == "off":
        node.auto_gaming_until = None
    node.updated_at = utc_now()
    session.add(AuditEvent(
        actor_type="dashboard", actor_id=node.id, action="node.game-settings.updated",
        details=json.dumps({"game_tracking": game_tracking, "auto_gaming_mode": auto_gaming_mode}, separators=(",", ":")),
    ))
    session.commit()
    session.refresh(node)
    return node


def correct_game_match(session: Session, game_id: str, steam_app_id: int | None) -> Game | None:
    """Store a commander's Steam match; the metadata loop then fetches it again."""
    game = session.get(Game, game_id)
    if game is None:
        return None
    game.steam_app_id = steam_app_id
    game.manual_match = True
    game.match_state = "pending" if steam_app_id else "none"
    game.metadata_attempts = 0
    game.metadata_checked_at = None
    if steam_app_id is None:
        game.store_name = game.description = game.release_date = None
        game.genres, game.developers = [], []
        if game.artwork_source != "upload":
            game.header_image = game.header_content_type = game.artwork_source = None
        # Without Steam the SteamGridDB lookup may find a banner instead.
        game.artwork_checked_at = None
    session.add(AuditEvent(
        actor_type="dashboard", actor_id=game.id, action="game.match.updated",
        details=json.dumps({"steam_app_id": steam_app_id}, separators=(",", ":")),
    ))
    session.commit()
    session.refresh(game)
    return game


ARTWORK_MAX_BYTES = 3 * 1024 * 1024


def artwork_content_type(data: bytes) -> str | None:
    """Return the image type from the file signature; the client header is ignored."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def set_custom_artwork(session: Session, game_id: str, data: bytes, actor_id: str, origin: str = "dashboard") -> Game | None:
    """Store a banner chosen in the dashboard; it is never replaced automatically.

    ``origin`` is "dashboard" for an uploaded file and "steamgriddb" for a
    banner a commander picked from the search; both count as hand-picked.
    """
    content_type = artwork_content_type(data)
    if content_type is None or len(data) > ARTWORK_MAX_BYTES:
        raise ValueError("unsupported image")
    game = session.get(Game, game_id)
    if game is None:
        return None
    game.header_image, game.header_content_type, game.artwork_source = data, content_type, "upload"
    session.add(AuditEvent(
        actor_type="dashboard", actor_id=actor_id, action="game.artwork.uploaded",
        details=json.dumps({"game_id": game.id, "bytes": len(data), "content_type": content_type, "origin": origin}, separators=(",", ":")),
    ))
    session.commit()
    session.refresh(game)
    return game


def remove_custom_artwork(session: Session, game_id: str, actor_id: str) -> Game | None:
    """Drop an uploaded banner; Steam or SteamGridDB artwork is fetched again."""
    game = session.get(Game, game_id)
    if game is None:
        return None
    if game.artwork_source == "upload":
        game.header_image = game.header_content_type = game.artwork_source = None
        game.artwork_checked_at = None
        if game.steam_app_id is not None:
            game.match_state = "pending"
            game.metadata_attempts = 0
            game.metadata_checked_at = None
        session.add(AuditEvent(
            actor_type="dashboard", actor_id=actor_id, action="game.artwork.removed",
            details=json.dumps({"game_id": game.id}, separators=(",", ":")),
        ))
        session.commit()
        session.refresh(game)
    return game


def playtime_statistics(
    session: Session,
    *,
    days: int,
    node_id: str | None,
    utc_offset_minutes: int,
    now: datetime | None = None,
    node_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Summarise play sessions; ``days == 0`` covers all recorded history."""
    current = now or utc_now()
    window_start = current - timedelta(days=days) if days else None
    query = select(GameSession)
    if window_start is not None:
        query = query.where(GameSession.ended_at >= window_start)
    if node_id:
        query = query.where(GameSession.node_id == node_id)
    if node_ids is not None:
        query = query.where(GameSession.node_id.in_(node_ids))
    sessions = session.scalars(query.order_by(GameSession.started_at)).all()
    offset = timedelta(minutes=utc_offset_minutes)
    nodes = {node.id: node.display_name for node in session.scalars(select(Node)).all()}

    per_game: dict[str | None, dict[str, Any]] = {}
    per_node: dict[str, float] = defaultdict(float)
    per_day: dict[str, float] = defaultdict(float)
    heatmap = [[0.0] * 24 for _ in range(7)]
    longest: dict[str, Any] | None = None
    total = 0.0
    for item in sessions:
        start, end = _aware(item.started_at), _aware(item.ended_at)
        if window_start is not None and start < window_start:
            start = window_start
        seconds = max(0.0, (end - start).total_seconds())
        if seconds <= 0:
            continue
        total += seconds
        per_node[item.node_id] += seconds
        game = item.game
        entry = per_game.setdefault(item.game_id, {
            "game_id": item.game_id,
            "title": game.title if game else None,
            "launcher": game.launcher if game else None,
            "has_artwork": bool(game and game.header_content_type),
            "custom_artwork": bool(game and game.artwork_source == "upload"),
            "genres": list(game.genres or []) if game else [],
            "seconds": 0.0, "sessions": 0, "last_played_at": end, "hardware": {}, "energy_wh": 0.0,
        })
        entry["seconds"] += seconds
        entry["sessions"] += 1
        entry["last_played_at"] = max(entry["last_played_at"], end)
        for name, (value_sum, count, peak) in (item.hardware or {}).items():
            if name == "energy_wh":
                entry["energy_wh"] += value_sum
                continue
            aggregate = entry["hardware"].setdefault(name, [0.0, 0.0, peak])
            aggregate[0] += value_sum
            aggregate[1] += count
            aggregate[2] = max(aggregate[2], peak)
        if longest is None or seconds > longest["seconds"]:
            longest = {"title": game.title if game else None, "node_name": nodes.get(item.node_id), "seconds": round(seconds), "started_at": start}
        _distribute(start + offset, end + offset, per_day, heatmap)

    games = sorted(per_game.values(), key=lambda value: value["seconds"], reverse=True)
    for entry in games:
        entry["seconds"] = round(entry["seconds"])
        entry["energy_wh"] = round(entry["energy_wh"], 1)
        entry["hardware"] = {
            name: {"average": round(value_sum / count, 1), "max": round(peak, 1)}
            for name, (value_sum, count, peak) in entry["hardware"].items() if count
        }
    recent = sorted(sessions, key=lambda value: _aware(value.ended_at), reverse=True)[:15]
    return {
        "days": days,
        "total_seconds": round(total),
        "session_count": sum(entry["sessions"] for entry in games),
        "game_count": len([entry for entry in games if entry["game_id"]]),
        "longest_session": longest,
        "games": games,
        "nodes": sorted(
            ({"node_id": key, "display_name": nodes.get(key, key), "seconds": round(value)} for key, value in per_node.items()),
            key=lambda value: value["seconds"], reverse=True,
        ),
        "daily": [{"date": key, "seconds": round(value)} for key, value in sorted(per_day.items())],
        "heatmap": [[round(value) for value in row] for row in heatmap],
        "recent_sessions": [
            {
                "session_id": value.id,
                "game_id": value.game_id,
                "title": value.game.title if value.game else None,
                "node_name": nodes.get(value.node_id, value.node_id),
                "started_at": _aware(value.started_at),
                "ended_at": _aware(value.ended_at),
                "seconds": round((_aware(value.ended_at) - _aware(value.started_at)).total_seconds()),
            }
            for value in recent
        ],
    }


def normalized_title(title: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", title.casefold().replace("&", "and"))


def _game_for(session: Session, reported: ReportedGame) -> Game:
    title = reported.title or ""
    launcher = reported.launcher or "other"
    if reported.app_id and launcher in LAUNCHERS:
        key = f"{launcher}:{reported.app_id}"
    else:
        key = f"name:{normalized_title(title) or title.casefold()}"
    game = session.scalar(select(Game).where(Game.key == key[:192]))
    if game is None:
        steam_app_id = int(reported.app_id) if launcher == "steam" and reported.app_id and reported.app_id.isdigit() else None
        game = Game(key=key[:192], title=title, launcher=launcher, steam_app_id=steam_app_id, genres=[], developers=[])
        session.add(game)
        session.flush()
    return game


def _distribute(start: datetime, end: datetime, per_day: dict[str, float], heatmap: list[list[float]]) -> None:
    """Spread a session over local calendar days and weekday/hour cells."""
    cursor = start
    while cursor < end:
        boundary = min(end, cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        seconds = (boundary - cursor).total_seconds()
        per_day[cursor.date().isoformat()] += seconds
        heatmap[cursor.weekday()][cursor.hour] += seconds
        cursor = boundary


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
