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

from ncc_server.models import AuditEvent, Game, GameSession, Node, utc_now

# Points of the same game closer than this belong to one session. It also
# bridges loading screens and a quick restart of the game.
SESSION_GAP = timedelta(minutes=5)
# How long automatic gaming mode stays on after the last point with a game.
AUTO_GAMING_GRACE = timedelta(minutes=5)
# Buffered points from the past must not switch gaming mode on again.
AUTO_GAMING_RECENT = timedelta(minutes=2)
# The now-playing card disappears once no point arrived for this long.
NOW_PLAYING_STALE = timedelta(seconds=90)
GAME_TRACKING_LEVELS = ("off", "presence", "titles")
LAUNCHERS = {"steam", "epic", "gog", "xbox"}


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
        current.started_at = min(_aware(current.started_at), recorded_at)
        current.ended_at = max(_aware(current.ended_at), recorded_at)
    else:
        current = GameSession(node_id=node.id, game_id=game_id, started_at=recorded_at, ended_at=recorded_at, sample_count=0, hardware={})
        session.add(current)
    current.sample_count += 1
    hardware = dict(current.hardware or {})
    for name, value in _hardware_values(metrics).items():
        total, count, peak = hardware.get(name, [0.0, 0.0, value])
        hardware[name] = [round(total + value, 3), count + 1, max(peak, value)]
    current.hardware = hardware
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
        game.store_name = game.description = game.release_date = game.header_content_type = None
        game.header_image = None
        game.genres, game.developers = [], []
    session.add(AuditEvent(
        actor_type="dashboard", actor_id=game.id, action="game.match.updated",
        details=json.dumps({"steam_app_id": steam_app_id}, separators=(",", ":")),
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
) -> dict[str, Any]:
    """Summarise play sessions; ``days == 0`` covers all recorded history."""
    current = now or utc_now()
    window_start = current - timedelta(days=days) if days else None
    query = select(GameSession)
    if window_start is not None:
        query = query.where(GameSession.ended_at >= window_start)
    if node_id:
        query = query.where(GameSession.node_id == node_id)
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
            "genres": list(game.genres or []) if game else [],
            "seconds": 0.0, "sessions": 0, "last_played_at": end, "hardware": {},
        })
        entry["seconds"] += seconds
        entry["sessions"] += 1
        entry["last_played_at"] = max(entry["last_played_at"], end)
        for name, (value_sum, count, peak) in (item.hardware or {}).items():
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


def _hardware_values(metrics: dict[str, object]) -> dict[str, float]:
    raw_cpu = metrics.get("cpu")
    cpu: dict[str, object] = raw_cpu if isinstance(raw_cpu, dict) else {}
    gpu = _first(metrics.get("gpus"))
    lhm_gpu = _first(metrics.get("lhm_gpus"))
    candidates = {
        "cpu_percent": cpu.get("percent"),
        "cpu_temperature_c": cpu.get("temperature_c"),
        "cpu_power_w": cpu.get("power_w"),
        "gpu_percent": gpu.get("percent"),
        # LibreHardwareMonitor has the more precise GPU sensors where present.
        "gpu_temperature_c": _number(lhm_gpu.get("temperature_c")) or gpu.get("temperature_c"),
        "gpu_power_w": _number(lhm_gpu.get("power_w")) or gpu.get("power_w"),
    }
    return {
        name: float(value) for name, value in candidates.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    }


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _first(value: object) -> dict[str, object]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


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
