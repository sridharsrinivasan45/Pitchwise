"""
Engine adapter — the ONLY module that talks to the underlying rating engine.

Currently this reads pre-computed ball events, ratings snapshots, and moments
from MongoDB (seeded via data/seed_curated.py). When the real Python impact
engine is dropped into backend/engine/core/ (Phase 2), we swap the internals
of these functions without touching any callers.
"""
from __future__ import annotations
from typing import AsyncIterator, Optional
from core.db import get_db
from engine.contracts import (
    BallEvent, RatingBreakdown, RatingComponent, ImpactRow,
    MomentumPoint, Moment, MatchState, MatchSummary,
)


async def list_matches(featured_only: bool = False) -> list[MatchSummary]:
    db = get_db()
    q = {"featured": True} if featured_only else {}
    docs = await db.matches.find(q, {"_id": 0}).to_list(100)
    return [MatchSummary(**d) for d in docs]


async def get_match(match_id: str) -> Optional[MatchSummary]:
    db = get_db()
    doc = await db.matches.find_one({"match_id": match_id}, {"_id": 0})
    return MatchSummary(**doc) if doc else None


async def stream_balls(match_id: str, from_ball: int = 0) -> AsyncIterator[BallEvent]:
    """Yield ball events in order. In replay mode the caller adds pacing."""
    db = get_db()
    cursor = db.balls.find(
        {"match_id": match_id},
        {"_id": 0},
    ).sort([("innings", 1), ("over", 1), ("ball", 1)]).skip(from_ball)
    async for doc in cursor:
        yield BallEvent(**doc)


async def get_ball_by_id(ball_id: str) -> Optional[BallEvent]:
    db = get_db()
    doc = await db.balls.find_one({"ball_id": ball_id}, {"_id": 0})
    return BallEvent(**doc) if doc else None


async def get_match_state(match_id: str, at_ball: Optional[int] = None) -> Optional[MatchState]:
    """Full state up to (and including) `at_ball` (index). None = full match."""
    db = get_db()
    match = await db.matches.find_one({"match_id": match_id}, {"_id": 0})
    if not match:
        return None

    ball_q = {"match_id": match_id}
    balls_cursor = db.balls.find(ball_q, {"_id": 0}).sort([("innings", 1), ("over", 1), ("ball", 1)])
    balls = await balls_cursor.to_list(1000)
    if at_ball is not None:
        balls = balls[: at_ball + 1]

    if not balls:
        return MatchState(match_id=match_id, current_over=0, current_ball=0)

    last = balls[-1]

    # Momentum series
    momentum = [
        MomentumPoint(
            ball_id=b["ball_id"], over=b["over"], ball=b["ball"], wp=b["wp_after"],
        )
        for b in balls
    ]

    # Top impact ratings at this point — latest snapshot PER PLAYER up to current sequence
    max_seq = len(balls) - 1
    pipeline = [
        {"$match": {"match_id": match_id, "sequence": {"$lte": max_seq}}},
        {"$sort": {"sequence": 1}},
        {"$group": {
            "_id": "$player_id",
            "final_rating": {"$last": "$final_rating"},
            "delta": {"$last": "$delta"},
            "after_ball_id": {"$last": "$after_ball_id"},
        }},
        {"$sort": {"final_rating": -1}},
        {"$limit": 6},
    ]
    rating_docs = await db.ratings_snapshots.aggregate(pipeline).to_list(6)

    top_impact: list[ImpactRow] = []
    for r in rating_docs:
        player = await db.players.find_one({"player_id": r["_id"]}, {"_id": 0})
        if not player:
            continue
        spark_docs = await db.ratings_snapshots.find(
            {"match_id": match_id, "player_id": r["_id"], "sequence": {"$lte": max_seq}},
            {"_id": 0, "final_rating": 1},
        ).sort("sequence", 1).to_list(1000)
        sparkline = [s["final_rating"] for s in spark_docs][-12:]
        top_impact.append(ImpactRow(
            player_id=player["player_id"],
            player_name=player["name"],
            role=player.get("role", "batter"),
            team=player.get("current_team", ""),
            rating=r["final_rating"],
            delta=r.get("delta", 0.0),
            sparkline=sparkline,
        ))

    # Latest moment up to now
    moment_doc = await db.moments.find_one(
        {"match_id": match_id, "sequence": {"$lte": len(balls) - 1}},
        {"_id": 0},
        sort=[("sequence", -1)],
    )
    latest_moment = Moment(**{k: v for k, v in moment_doc.items() if k != "sequence"}) if moment_doc else None

    return MatchState(
        match_id=match_id,
        current_over=last["over"],
        current_ball=last["ball"],
        latest_ball_id=last["ball_id"],
        top_impact=top_impact,
        momentum=momentum,
        latest_moment=latest_moment,
    )


async def get_moments(match_id: str, top_n: int = 5) -> list[Moment]:
    db = get_db()
    docs = await db.moments.find(
        {"match_id": match_id}, {"_id": 0},
    ).sort("impact_score", -1).limit(top_n).to_list(top_n)
    return [Moment(**{k: v for k, v in d.items() if k != "sequence"}) for d in docs]


async def get_rating_breakdown(match_id: str, player_id: str, at_ball_id: Optional[str] = None) -> Optional[RatingBreakdown]:
    db = get_db()
    q = {"match_id": match_id, "player_id": player_id}
    if at_ball_id:
        q["after_ball_id"] = at_ball_id
        doc = await db.ratings_snapshots.find_one(q, {"_id": 0})
    else:
        doc = await db.ratings_snapshots.find_one(q, {"_id": 0}, sort=[("sequence", -1)])
    if not doc:
        return None
    player = await db.players.find_one({"player_id": player_id}, {"_id": 0})
    return RatingBreakdown(
        player_id=player_id,
        player_name=player["name"] if player else player_id,
        match_id=match_id,
        after_ball_id=doc.get("after_ball_id"),
        base_rating=doc["base_rating"],
        components=[RatingComponent(**c) for c in doc.get("components", [])],
        final_rating=doc["final_rating"],
        delta_from_previous=doc.get("delta", 0.0),
        narrative=doc.get("narrative", ""),
    )


async def get_impact_board(match_id: str, at_ball_id: Optional[str] = None) -> list[ImpactRow]:
    state = await get_match_state(match_id, at_ball=None)
    return state.top_impact if state else []
