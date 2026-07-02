"""Rating breakdown routes — powers the WhySheet."""
from fastapi import APIRouter, HTTPException, Query
from engine import adapter

router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.get("/{match_id}/{player_id}")
async def get_breakdown(
    match_id: str,
    player_id: str,
    at_ball_id: str | None = Query(None, description="Optional ball_id snapshot; latest if omitted"),
):
    b = await adapter.get_rating_breakdown(match_id, player_id, at_ball_id=at_ball_id)
    if not b:
        raise HTTPException(404, "Rating snapshot not found")
    return b.model_dump()
