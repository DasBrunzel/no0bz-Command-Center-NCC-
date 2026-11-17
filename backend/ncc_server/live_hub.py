"""In-memory hub for app nodes that keep a live WebSocket open (the Android app).

The hub only lives in this server process and stores nothing in the database:

* which app connections are open per node,
* which nodes a dashboard is currently looking at (viewers expire after a
  short TTL unless the dashboard keeps asking),
* the newest live telemetry sample per node, and
* the active alerts last sent to the apps, to push only what changed.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.models import AlertState, Node

VIEWER_TTL_SECONDS = 15.0
LIVE_TTL_SECONDS = 15.0
LIVE_INTERVAL_MS = 2000
QUEUE_SIZE = 200


@dataclass(frozen=True)
class AppAlert:
    alert_id: str
    node_id: str
    node_name: str
    kind: str
    severity: str
    message: str
    opened_at: str
    owner_user_id: str | None = None

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("owner_user_id")
        return data


@dataclass(eq=False)
class Subscriber:
    node_id: str
    commander: bool
    owner_user_id: str | None
    queue: asyncio.Queue[dict[str, Any]]

    def put(self, message: dict[str, Any]) -> None:
        # A slow phone must never block the server: drop the oldest message.
        if self.queue.full():
            with suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
        self.queue.put_nowait(message)


@dataclass
class LivePoint:
    received: float
    recorded_at: str
    metrics: dict[str, Any]


class LiveHub:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._subscribers: dict[str, set[Subscriber]] = {}
        self._viewers: dict[str, float] = {}
        self._live: dict[str, LivePoint] = {}
        self._alerts: dict[str, AppAlert] = {}
        self._alerts_enabled = True

    # ── connections ──────────────────────────────────────────────────────

    def subscribe(
        self,
        node_id: str,
        *,
        commander: bool,
        owner_user_id: str | None,
        snapshot: list[AppAlert] | None = None,
    ) -> Subscriber:
        subscriber = Subscriber(node_id, commander, owner_user_id, asyncio.Queue(maxsize=QUEUE_SIZE))
        self._subscribers.setdefault(node_id, set()).add(subscriber)
        if snapshot is not None:
            visible = [alert.public() for alert in snapshot if _allowed(subscriber, alert)]
            subscriber.put({"type": "alert.snapshot", "alerts": visible})
        if self.viewer_active(node_id):
            subscriber.put({"type": "viewer.present", "interval_ms": LIVE_INTERVAL_MS})
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        group = self._subscribers.get(subscriber.node_id)
        if group is not None:
            group.discard(subscriber)
            if not group:
                del self._subscribers[subscriber.node_id]
                self._live.pop(subscriber.node_id, None)

    def connected(self, node_id: str) -> bool:
        return bool(self._subscribers.get(node_id))

    # ── live telemetry ───────────────────────────────────────────────────

    def store_live(self, node_id: str, recorded_at: str, metrics: dict[str, Any]) -> None:
        self._live[node_id] = LivePoint(self._clock(), recorded_at, metrics)

    def latest_live(self, node_id: str) -> LivePoint | None:
        point = self._live.get(node_id)
        if point is None or self._clock() - point.received > LIVE_TTL_SECONDS:
            return None
        return point

    # ── dashboard viewers ────────────────────────────────────────────────

    def viewer_active(self, node_id: str) -> bool:
        expires = self._viewers.get(node_id)
        return expires is not None and expires > self._clock()

    def touch_viewer(self, node_id: str) -> None:
        was_active = self.viewer_active(node_id)
        self._viewers[node_id] = self._clock() + VIEWER_TTL_SECONDS
        if not was_active:
            self._broadcast(node_id, {"type": "viewer.present", "interval_ms": LIVE_INTERVAL_MS})

    def expire_viewers(self) -> None:
        now = self._clock()
        for node_id, expires in list(self._viewers.items()):
            if expires <= now:
                del self._viewers[node_id]
                self._broadcast(node_id, {"type": "viewer.gone"})

    # ── alerts ───────────────────────────────────────────────────────────

    def publish_alerts(self, active: list[AppAlert], enabled: bool) -> None:
        """Send alerts that opened or resolved since the last evaluation."""
        current = {alert.alert_id: alert for alert in active}
        previous = self._alerts
        self._alerts = current
        just_enabled = enabled and not self._alerts_enabled
        self._alerts_enabled = enabled
        if not enabled:
            return
        if just_enabled:
            # The owner switched app alerts back on: resend the full picture.
            for subscriber in self._all_subscribers():
                visible = [alert.public() for alert in active if _allowed(subscriber, alert)]
                subscriber.put({"type": "alert.snapshot", "alerts": visible})
            return
        opened = [alert for alert_id, alert in current.items() if alert_id not in previous]
        resolved = [alert for alert_id, alert in previous.items() if alert_id not in current]
        for subscriber in self._all_subscribers():
            for alert in opened:
                if _allowed(subscriber, alert):
                    subscriber.put({"type": "alert.new", "alert": alert.public()})
            for alert in resolved:
                if _allowed(subscriber, alert):
                    subscriber.put({"type": "alert.resolved", "alert": alert.public()})

    # ── chat ─────────────────────────────────────────────────────────────

    def publish_chat(self, message: dict[str, Any]) -> None:
        """Push a new Fleet chat message to every connected app."""
        for subscriber in self._all_subscribers():
            subscriber.put({"type": "chat.new", "message": message})

    # ── helpers ──────────────────────────────────────────────────────────

    def _broadcast(self, node_id: str, message: dict[str, Any]) -> None:
        for subscriber in self._subscribers.get(node_id, set()):
            subscriber.put(message)

    def _all_subscribers(self) -> list[Subscriber]:
        return [subscriber for group in self._subscribers.values() for subscriber in group]


def _allowed(subscriber: Subscriber, alert: AppAlert) -> bool:
    """Commander devices see every alert, a friend's device only its owner's devices."""
    if subscriber.commander:
        return True
    return subscriber.owner_user_id is not None and alert.owner_user_id == subscriber.owner_user_id


def active_app_alerts(session: Session) -> list[AppAlert]:
    rows = session.execute(
        select(AlertState, Node.display_name, Node.owner_user_id)
        .join(Node, Node.id == AlertState.node_id)
        .where(AlertState.active.is_(True))
        .order_by(AlertState.opened_at)
    ).all()
    return [
        AppAlert(
            alert_id=alert.id,
            node_id=alert.node_id,
            node_name=name,
            kind=alert.kind,
            severity=alert.severity,
            message=alert.message,
            opened_at=alert.opened_at.isoformat() if alert.opened_at else "",
            owner_user_id=owner,
        )
        for alert, name, owner in rows
    ]
