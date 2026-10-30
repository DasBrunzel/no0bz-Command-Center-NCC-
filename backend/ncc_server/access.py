"""Which devices a dashboard identity may see and change.

Commanders and beta testers see every device. A friend sees only the devices
they own; a commander may additionally let a friend see the statistics of all
devices. Every node-specific endpoint goes through these helpers, so a friend
never learns that another device exists: it simply reports "not found".
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.auth import DashboardIdentity
from ncc_server.models import Node


def visible_node_ids(session: Session, identity: DashboardIdentity, *, statistics: bool = False) -> set[str] | None:
    """Return the node ids the identity may see, or None for all of them."""
    if not identity.is_friend:
        return None
    if statistics and identity.full_statistics:
        return None
    if identity.user_id is None:
        return set()
    return set(session.scalars(select(Node.id).where(Node.owner_user_id == identity.user_id)).all())


def can_see_node(session: Session, identity: DashboardIdentity, node_id: str, *, statistics: bool = False) -> bool:
    allowed = visible_node_ids(session, identity, statistics=statistics)
    return allowed is None or node_id in allowed


def visible_node(session: Session, identity: DashboardIdentity, node_id: str) -> Node:
    node = session.get(Node, node_id)
    if node is None or not can_see_node(session, identity, node_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="node not found")
    return node


def manageable_node(session: Session, identity: DashboardIdentity, node_id: str) -> Node:
    """A commander manages every device, a friend only their own."""
    node = visible_node(session, identity, node_id)
    if identity.access_role == "commander":
        return node
    if identity.is_friend and identity.user_id is not None and node.owner_user_id == identity.user_id:
        return node
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commander access required")
