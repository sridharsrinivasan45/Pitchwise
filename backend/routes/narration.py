"""Match narration route — PitchWise's explanation layer.

Endpoint
--------
GET /api/matches/{match_id}/narration?refresh=<0|1>&polish=<1|0>

Returns:
  {
    match_id, context: {teams_short, winner_short, result_summary, final_score},
    verdict: {sentence, polished, archetype, evidence},
    turning_point: {sentence, polished, evidence} | null,
    players: [{sentence, polished, evidence}, ...],
  }
"""
from fastapi import APIRouter, HTTPException, Query
from services.narrator import get_or_build_narration, narrate_match
from core.db import get_db

router = APIRouter(prefix="/matches", tags=["narration"])


@router.get("/{match_id}/narration")
async def get_narration(
    match_id: str,
    refresh: bool = Query(False, description="Skip cache and recompute"),
    polish: bool = Query(True, description="Route sentences through LLM polish"),
):
    if refresh:
        db = get_db()
        await db.narrations.delete_one({"match_id": match_id})
        payload = await narrate_match(match_id, polish=polish)
    else:
        payload = await get_or_build_narration(match_id, polish=polish)
    if payload is None:
        raise HTTPException(404, "Match not found or has no ball data")
    return payload
