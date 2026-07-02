"""Match routes."""
from fastapi import APIRouter, HTTPException, Query
from engine import adapter

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
async def list_matches(featured: bool = Query(False)):
    matches = await adapter.list_matches(featured_only=featured)
    return {"matches": [m.model_dump() for m in matches]}


@router.get("/{match_id}")
async def get_match(match_id: str):
    m = await adapter.get_match(match_id)
    if not m:
        raise HTTPException(404, "Match not found")
    return m.model_dump()


@router.get("/{match_id}/state")
async def get_match_state(match_id: str, at_ball: int | None = Query(None)):
    s = await adapter.get_match_state(match_id, at_ball=at_ball)
    if not s:
        raise HTTPException(404, "Match not found")
    return s.model_dump()


@router.get("/{match_id}/moments")
async def get_moments(match_id: str, top_n: int = Query(5, ge=1, le=20)):
    moments = await adapter.get_moments(match_id, top_n=top_n)
    return {"moments": [m.model_dump() for m in moments]}


@router.get("/{match_id}/impact-board")
async def get_impact_board(match_id: str):
    board = await adapter.get_impact_board(match_id)
    return {"impact_board": [r.model_dump() for r in board]}
