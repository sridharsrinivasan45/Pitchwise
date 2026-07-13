"""
SSE replay stream for a match. Emits one `tick` per ball with the assembled
state snapshot at that ball — reusing engine.adapter.get_match_state.

Client controls:
  ?from_ball=<int>   (resume from a specific ball sequence, default 0)
  ?speed=<float>     (1.0 = default cadence; 2 = twice as fast; 0.5 = slow-mo)

Pacing is server-side (asyncio.sleep). Client disconnects are honored via
Request.is_disconnected().
"""
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from engine import adapter

router = APIRouter(prefix="/matches", tags=["stream"])

# Base cadence per ball, in seconds, at speed=1.0. Feels cricket-paced without being sleepy.
BASE_BALL_INTERVAL = 0.9


def _narration_for(ball: dict, top_impact: list, ball_idx: int, total: int) -> str:
    """Static, event-based narration line. Replaced by AI narrator in M5."""
    over_str = f"O{ball['over']+1}.{ball['ball']}"
    if ball.get("is_wicket"):
        return f"WICKET at {over_str}. Pressure index {ball['pressure_index']:.1f} — the bowler struck at the critical moment."
    runs = ball.get("runs_batter", 0)
    phase = ball.get("phase", "middle")
    if runs == 6:
        return f"SIX at {over_str}. Pressure {ball['pressure_index']:.1f}, this one hurts."
    if runs == 4:
        return f"FOUR at {over_str}. Boundary in the {phase} — momentum inches."
    if runs == 0 and phase == "death":
        return f"Dot ball at {over_str}. In the death, a dot IS an event — pressure {ball['pressure_index']:.1f}."
    if ball_idx == 0:
        return "PitchWise is watching. The innings begins."
    if ball_idx >= total - 1:
        return "That's the innings. Explore the ratings to see who changed this match."
    if top_impact:
        top = top_impact[0]
        return f"{top.player_name} leads the impact board at {top.rating:.1f}."
    return f"{ball.get('commentary', 'Play on.')}"


async def _tick_generator(match_id: str, request: Request, from_ball: int = 0, speed: float = 1.0):
    """Yield SSE messages, one per ball, paced by `speed`."""
    # Fetch static match info
    match = await adapter.get_match(match_id)
    if not match:
        yield f"event: error\ndata: {json.dumps({'error': 'match not found'})}\n\n"
        return

    # Enumerate balls (list, so we know the total up-front)
    balls: list[dict] = []
    async for b in adapter.stream_balls(match_id):
        balls.append(b.model_dump())
    total = len(balls)
    if total == 0:
        yield f"event: end\ndata: {json.dumps({'reason': 'no balls'})}\n\n"
        return

    # Emit an initial `meta` event with total ball count so the client can render a progress bar
    yield f"event: meta\ndata: {json.dumps({'total_balls': total, 'from_ball': from_ball, 'speed': speed})}\n\n"

    interval = max(0.05, BASE_BALL_INTERVAL / max(0.1, speed))

    for i in range(from_ball, total):
        if await request.is_disconnected():
            return
        state = await adapter.get_match_state(match_id, at_ball=i)
        if not state:
            continue
        ball = balls[i]
        narration = _narration_for(ball, state.top_impact, i, total)

        payload = {
            "seq": i,
            "total": total,
            "ball": ball,
            "state": {
                "current_over": state.current_over,
                "current_ball": state.current_ball,
                "latest_ball_id": state.latest_ball_id,
                "top_impact": [r.model_dump() for r in state.top_impact],
                "momentum": [m.model_dump() for m in state.momentum],
                "latest_moment": state.latest_moment.model_dump() if state.latest_moment else None,
            },
            "narration": narration,
        }
        yield f"event: tick\ndata: {json.dumps(payload)}\n\n"
        # For the very first ball, no wait — get on screen immediately
        if i > from_ball:
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return

    yield f"event: end\ndata: {json.dumps({'total_balls': total})}\n\n"


@router.get("/{match_id}/stream")
async def stream_match(
    match_id: str,
    request: Request,
    from_ball: int = Query(0, ge=0),
    speed: float = Query(1.0, gt=0.1, le=10.0),
    mode: str = Query("replay"),
):
    # Verify match exists (fail fast rather than in the stream)
    match = await adapter.get_match(match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    return StreamingResponse(
        _tick_generator(match_id, request, from_ball=from_ball, speed=speed),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
