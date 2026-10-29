from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from ncc.security import limited
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from ncc_server.auth import database_session, require_commander_access, require_dashboard_access
from ncc_server.fleet_service import fleet_node
from ncc_server.game_service import correct_game_match, playtime_statistics, update_game_settings
from ncc_server.models import Game
from ncc_server.schemas import (
    FleetGameSettingsRequest,
    FleetNodeResponse,
    GameMatchUpdateRequest,
    GameResponse,
)

router = APIRouter(
    prefix="/fleet",
    tags=["games"],
    dependencies=[Depends(require_dashboard_access), Depends(limited("v1-fleet-read", 300))],
)


@router.put(
    "/nodes/{node_id}/game-settings",
    response_model=FleetNodeResponse,
    dependencies=[Depends(require_commander_access)],
)
async def set_game_settings(
    node_id: str, payload: FleetGameSettingsRequest, request: Request, session: Session = Depends(database_session)
) -> FleetNodeResponse:
    node = update_game_settings(session, node_id, payload.game_tracking, payload.auto_gaming_mode)
    response = fleet_node(session, node.id, request.app.state.server_settings) if node else None
    if response is None:
        raise HTTPException(status_code=404, detail="node not found")
    return response


@router.get("/games/stats")
async def game_statistics(
    days: int = Query(default=30, ge=0, le=3660),
    node_id: str | None = Query(default=None, max_length=36),
    utc_offset_minutes: int = Query(default=0, ge=-840, le=840),
    session: Session = Depends(database_session),
) -> dict[str, Any]:
    return playtime_statistics(session, days=days, node_id=node_id, utc_offset_minutes=utc_offset_minutes)


@router.get("/games", response_model=list[GameResponse])
async def games(session: Session = Depends(database_session)) -> list[GameResponse]:
    return [_game_response(game) for game in session.scalars(select(Game).order_by(Game.title)).all()]


@router.patch("/games/{game_id}", response_model=GameResponse, dependencies=[Depends(require_commander_access)])
async def update_game_match(
    game_id: str, payload: GameMatchUpdateRequest, session: Session = Depends(database_session)
) -> GameResponse:
    game = correct_game_match(session, game_id, payload.steam_app_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return _game_response(game)


@router.get("/games/{game_id}/artwork", response_class=Response)
async def game_artwork(game_id: str, session: Session = Depends(database_session)) -> Response:
    game = session.get(Game, game_id, options=[undefer(Game.header_image)])
    if game is None or not game.header_image or not game.header_content_type:
        raise HTTPException(status_code=404, detail="artwork not found")
    return Response(content=game.header_image, media_type=game.header_content_type)


def _game_response(game: Game) -> GameResponse:
    return GameResponse(
        game_id=game.id,
        title=game.title,
        launcher=game.launcher,
        steam_app_id=game.steam_app_id,
        match_state=game.match_state,
        manual_match=game.manual_match,
        store_name=game.store_name,
        description=game.description,
        genres=list(game.genres or []),
        developers=list(game.developers or []),
        release_date=game.release_date,
        has_artwork=bool(game.header_content_type),
    )
