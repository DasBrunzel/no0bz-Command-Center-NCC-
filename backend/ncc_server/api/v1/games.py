from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from ncc.security import limited
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from ncc_server.access import can_see_node, manageable_node, visible_node_ids
from ncc_server.artwork_search import ArtworkSearchCache, full_image, preview, search_candidates
from ncc_server.auth import (
    DashboardIdentity,
    database_session,
    require_commander_access,
    require_dashboard_access,
    require_dashboard_identity,
)
from ncc_server.fleet_service import fleet_node
from ncc_server.game_service import (
    ARTWORK_MAX_BYTES,
    correct_game_match,
    playtime_statistics,
    remove_custom_artwork,
    set_custom_artwork,
    update_game_settings,
)
from ncc_server.hardware_stats import hardware_statistics
from ncc_server.models import Game, GameSession
from ncc_server.schemas import (
    ArtworkCandidateResponse,
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


@router.put("/nodes/{node_id}/game-settings", response_model=FleetNodeResponse)
async def set_game_settings(
    node_id: str,
    payload: FleetGameSettingsRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> FleetNodeResponse:
    manageable_node(session, identity, node_id)
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
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> dict[str, Any]:
    node_ids = _statistics_scope(session, identity, node_id)
    return playtime_statistics(session, days=days, node_id=node_id, utc_offset_minutes=utc_offset_minutes, node_ids=node_ids)


@router.get("/hardware/stats")
async def hardware_stats(
    days: int = Query(default=30, ge=0, le=3660),
    node_id: str | None = Query(default=None, max_length=36),
    utc_offset_minutes: int = Query(default=0, ge=-840, le=840),
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> dict[str, Any]:
    node_ids = _statistics_scope(session, identity, node_id)
    return hardware_statistics(session, days=days, node_id=node_id, utc_offset_minutes=utc_offset_minutes, node_ids=node_ids)


@router.get("/games", response_model=list[GameResponse])
async def games(
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> list[GameResponse]:
    allowed = visible_node_ids(session, identity, statistics=True)
    query = select(Game).order_by(Game.title)
    if allowed is not None:
        # Only games that were played on a device the identity may see.
        query = query.where(Game.id.in_(select(GameSession.game_id).where(GameSession.node_id.in_(allowed))))
    return [_game_response(game) for game in session.scalars(query).all()]


def _statistics_scope(session: Session, identity: DashboardIdentity, node_id: str | None) -> set[str] | None:
    if node_id is not None and not can_see_node(session, identity, node_id, statistics=True):
        raise HTTPException(status_code=404, detail="node not found")
    return visible_node_ids(session, identity, statistics=True)


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


@router.put("/games/{game_id}/artwork", response_model=GameResponse, dependencies=[Depends(require_commander_access)])
async def upload_game_artwork(
    game_id: str,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> GameResponse:
    """Store a JPEG, PNG or WebP banner sent as the raw request body."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > ARTWORK_MAX_BYTES):
        raise HTTPException(status_code=413, detail="image too large")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > ARTWORK_MAX_BYTES:
            raise HTTPException(status_code=413, detail="image too large")
    try:
        game = set_custom_artwork(session, game_id, bytes(data), _actor(identity))
    except ValueError:
        raise HTTPException(status_code=415, detail="use a JPEG, PNG or WebP image") from None
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return _game_response(game)


@router.delete("/games/{game_id}/artwork", response_model=GameResponse, dependencies=[Depends(require_commander_access)])
async def delete_game_artwork(
    game_id: str,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> GameResponse:
    game = remove_custom_artwork(session, game_id, _actor(identity))
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return _game_response(game)


def _search_cache(request: Request) -> ArtworkSearchCache:
    cache = getattr(request.app.state, "artwork_search", None)
    if cache is None:
        cache = request.app.state.artwork_search = ArtworkSearchCache()
    return cache


def _steamgriddb_client(request: Request) -> httpx.AsyncClient:
    key = request.app.state.server_settings.steamgriddb_api_key.get_secret_value()
    if not key:
        raise HTTPException(status_code=503, detail="SteamGridDB ist auf dem Server nicht eingerichtet")
    # Tests hand in a mock transport; production uses the network.
    transport = getattr(request.app.state, "steamgriddb_transport", None)
    return httpx.AsyncClient(timeout=15, transport=transport, headers={"User-Agent": "no0bz-ncc-server"})


@router.get(
    "/games/{game_id}/artwork/candidates",
    response_model=list[ArtworkCandidateResponse],
    dependencies=[Depends(require_commander_access), Depends(limited("v1-artwork-search", 20))],
)
async def artwork_candidates(
    game_id: str,
    request: Request,
    query: str | None = Query(default=None, min_length=1, max_length=128),
    session: Session = Depends(database_session),
) -> list[ArtworkCandidateResponse]:
    """Search SteamGridDB for banners; the title of the game is the default query."""
    game = session.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    key = request.app.state.server_settings.steamgriddb_api_key.get_secret_value()
    async with _steamgriddb_client(request) as client:
        try:
            candidates = await search_candidates(client, (query or game.title).strip(), key)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="SteamGridDB antwortet gerade nicht") from exc
    _search_cache(request).put(game_id, candidates)
    return [
        ArtworkCandidateResponse(
            index=index, game_name=item.game_name, width=item.width, height=item.height, style=item.style,
            preview_url=f"/api/v1/fleet/games/{game_id}/artwork/candidates/{index}/preview",
        )
        for index, item in enumerate(candidates)
    ]


@router.get(
    "/games/{game_id}/artwork/candidates/{index}/preview",
    response_class=Response,
    dependencies=[Depends(require_commander_access)],
)
async def artwork_candidate_preview(game_id: str, index: int, request: Request) -> Response:
    candidate = _search_cache(request).get(game_id, index)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    async with _steamgriddb_client(request) as client:
        try:
            image = await preview(client, candidate)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="SteamGridDB antwortet gerade nicht") from exc
    if image is None:
        raise HTTPException(status_code=404, detail="preview not available")
    return Response(content=image[0], media_type=image[1], headers={"Cache-Control": "private, max-age=900"})


@router.post(
    "/games/{game_id}/artwork/candidates/{index}",
    response_model=GameResponse,
    dependencies=[Depends(require_commander_access), Depends(limited("v1-artwork-choose", 20))],
)
async def choose_artwork_candidate(
    game_id: str,
    index: int,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> GameResponse:
    """Store the chosen banner like an upload: it is never replaced automatically."""
    candidate = _search_cache(request).get(game_id, index)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    async with _steamgriddb_client(request) as client:
        try:
            image = await full_image(client, candidate)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="SteamGridDB antwortet gerade nicht") from exc
    if image is None:
        raise HTTPException(status_code=415, detail="use a JPEG, PNG or WebP image")
    try:
        game = set_custom_artwork(session, game_id, image[0], _actor(identity), origin="steamgriddb")
    except ValueError:
        raise HTTPException(status_code=415, detail="use a JPEG, PNG or WebP image") from None
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return _game_response(game)


def _actor(identity: DashboardIdentity) -> str:
    return identity.user_id or identity.username


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
        artwork_source=game.artwork_source,
    )
