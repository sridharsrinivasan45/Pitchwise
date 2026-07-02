"""
Engine adapter — thin translation layer.

This module is the ONLY interface between the product and the analytics engine.
It performs NO analytics. All ratings, WPA, and impact scores come from data
materialized by engine/pipeline.py (which calls engine/core/* unchanged).

The 8 public functions preserve the contracts consumed by routes/ and the
frontend. Their internals now read from Mongo collections populated by the
engine pipeline.
"""
from __future__ import annotations
from typing import AsyncIterator, Optional
from core.db import get_db
from data.team_aliases import resolve_team
from engine.contracts import (
    BallEvent, RatingBreakdown, RatingComponent, ImpactRow,
    MomentumPoint, Moment, MatchState, MatchSummary,
)


# ---------- Match catalog ----------

def _match_to_summary(doc: dict) -> MatchSummary:
    teams_raw = doc.get("teams", [])
    return MatchSummary(
        match_id=doc["match_id"],
        season=doc.get("season", ""),
        date=doc.get("date", ""),
        teams=[resolve_team(t)["name"] for t in teams_raw],
        team_short=[resolve_team(t)["short"] for t in teams_raw],
        venue=doc.get("venue", ""),
        format=doc.get("format", "T20"),
        status=doc.get("status", "time_machine"),
        featured=bool(doc.get("featured", False)),
        curation_slug=doc.get("curation_slug"),
        curation_title=doc.get("curation_title"),
        curation_hook=doc.get("curation_hook"),
        result_summary=doc.get("result_summary"),
        final_score=doc.get("final_score"),
        ball_count=int(doc.get("ball_count", 0)),
    )


async def list_matches(featured_only: bool = False) -> list[MatchSummary]:
    db = get_db()
    q = {"featured": True} if featured_only else {}
    docs = await db.matches.find(q, {"_id": 0}).sort([("date", -1)]).to_list(500)
    return [_match_to_summary(d) for d in docs]


async def get_match(match_id: str) -> Optional[MatchSummary]:
    db = get_db()
    doc = await db.matches.find_one({"match_id": match_id}, {"_id": 0})
    return _match_to_summary(doc) if doc else None


# ---------- Ball projection ----------

def _ball_uid(b: dict) -> str:
    """Synthesize the canonical ball_id used across snapshots/moments/UI.
    The balls collection historically stores a legal_ball_num-based ball_uid
    (e.g. `<m>-i2-109`), but the engine pipeline persists snapshots/moments
    keyed by an over.ball format (e.g. `<m>-i2-o17.6`). The API surface must
    speak the latter so WhySheet lookups match snapshot rows.
    """
    return f"{b['match_id']}-i{int(b['innings'])}-o{int(b['over'])}.{int(b['ball_in_over'])}"


def _ball_doc_to_event(b: dict) -> BallEvent:
    """Project a raw Mongo balls doc into the BallEvent contract."""
    return BallEvent(
        ball_id=_ball_uid(b),
        match_id=b["match_id"],
        innings=int(b["innings"]),
        over=int(b["over"]),
        ball=int(b["ball_in_over"]),
        batter_id=b.get("batter_id") or f"name:{b.get('batter','')}",
        bowler_id=b.get("bowler_id") or f"name:{b.get('bowler','')}",
        non_striker_id=b.get("non_striker_id"),
        runs_batter=int(b.get("runs_batter", 0)),
        runs_extras=int(b.get("runs_extras", 0)),
        runs_total=int(b.get("runs_total", 0)),
        is_wicket=bool(b.get("is_wicket", 0)),
        dismissal_type=b.get("dismissal_type"),
        dismissed_player_id=b.get("dismissed_player_id"),
        phase=b.get("phase", "middle"),
        pressure_index=float(min(9.9, max(1.0, abs(float(b.get("wpa", 0.0))) * 60 + 3.0))),  # display-only proxy from WPA
        difficulty=float(6.0),  # placeholder — engine has strength_multiplier per bowler-season, presentation-mapped
        wp_before=float(b.get("wp_before", 0.5)),
        wp_after=float(b.get("wp_after", 0.5)),
        batter_impact_delta=float(b.get("batter_wpa_adjusted", 0.0)),
        bowler_impact_delta=float(b.get("bowler_wpa", 0.0)),
        commentary="",
    )


async def stream_balls(match_id: str, from_ball: int = 0) -> AsyncIterator[BallEvent]:
    db = get_db()
    cursor = db.balls.find({"match_id": match_id}, {"_id": 0}).sort(
        [("innings", 1), ("over", 1), ("ball_in_over", 1)]
    ).skip(from_ball)
    async for b in cursor:
        yield _ball_doc_to_event(b)


async def get_ball_by_id(ball_id: str) -> Optional[BallEvent]:
    db = get_db()
    b = await db.balls.find_one({"ball_uid": ball_id}, {"_id": 0})
    return _ball_doc_to_event(b) if b else None


# ---------- Match state (momentum + impact board) ----------

async def get_match_state(match_id: str, at_ball: Optional[int] = None) -> Optional[MatchState]:
    db = get_db()
    if not await db.matches.find_one({"match_id": match_id}, {"_id": 1}):
        return None

    balls = await db.balls.find({"match_id": match_id}, {"_id": 0}).sort(
        [("innings", 1), ("over", 1), ("ball_in_over", 1)]
    ).to_list(500)
    if at_ball is not None:
        balls = balls[: at_ball + 1]
    if not balls:
        return MatchState(match_id=match_id, current_over=0, current_ball=0)

    last = balls[-1]
    momentum = [
        MomentumPoint(
            ball_id=_ball_uid(b),
            over=int(b["over"]), ball=int(b["ball_in_over"]),
            wp=float(b.get("wp_after", 0.5)),
        ) for b in balls
    ]

    # Top impact — latest snapshot per player from ratings_snapshots (engine-derived)
    max_seq = len(balls) - 1
    pipeline = [
        {"$match": {"match_id": match_id, "match_seq": {"$lte": max_seq}}},
        {"$sort": {"match_seq": 1}},
        {"$group": {
            "_id": "$player_id",
            "player_name": {"$last": "$player_name"},
            "role": {"$last": "$role"},
            "final_rating": {"$last": "$final_rating"},
            "delta": {"$last": "$delta"},
        }},
        {"$sort": {"final_rating": -1}},
        {"$limit": 6},
    ]
    top_docs = await db.ratings_snapshots.aggregate(pipeline).to_list(6)

    top_impact: list[ImpactRow] = []
    for r in top_docs:
        # Sparkline: recent rating trajectory
        spark_docs = await db.ratings_snapshots.find(
            {"match_id": match_id, "player_id": r["_id"], "match_seq": {"$lte": max_seq}},
            {"_id": 0, "final_rating": 1},
        ).sort("match_seq", 1).to_list(1000)
        sparkline = [s["final_rating"] for s in spark_docs][-12:]
        # Team AT MATCH TIME — look up a ball this player was involved in for this match
        role = r.get("role", "batter")
        team = ""
        team_field = "batting_team" if role == "batter" else "bowling_team"
        id_field = "batter_id" if role == "batter" else "bowler_id"
        ball_sample = await db.balls.find_one(
            {"match_id": match_id, id_field: r["_id"]},
            {"_id": 0, team_field: 1},
        )
        if ball_sample and ball_sample.get(team_field):
            team = resolve_team(ball_sample[team_field])["short"]
        top_impact.append(ImpactRow(
            player_id=r["_id"], player_name=r["player_name"], role=role,
            team=team, rating=float(r["final_rating"]),
            delta=float(r.get("delta", 0.0)), sparkline=sparkline,
        ))

    # Latest moment up to now
    latest_moment_doc = await db.moments.find_one(
        {"match_id": match_id, "sequence": {"$lte": max_seq}},
        {"_id": 0}, sort=[("sequence", -1)],
    )
    latest_moment = Moment(**{k: v for k, v in latest_moment_doc.items() if k != "sequence"}) if latest_moment_doc else None

    return MatchState(
        match_id=match_id,
        current_over=int(last["over"]),
        current_ball=int(last["ball_in_over"]),
        latest_ball_id=_ball_uid(last),
        top_impact=top_impact, momentum=momentum, latest_moment=latest_moment,
    )


async def get_moments(match_id: str, top_n: int = 5) -> list[Moment]:
    db = get_db()
    docs = await db.moments.find({"match_id": match_id}, {"_id": 0}).sort(
        "impact_score", -1
    ).limit(top_n).to_list(top_n)
    return [Moment(**{k: v for k, v in d.items() if k != "sequence"}) for d in docs]


async def get_impact_board(match_id: str, at_ball_id: Optional[str] = None) -> list[ImpactRow]:
    state = await get_match_state(match_id, at_ball=None)
    return state.top_impact if state else []


# ---------- Rating breakdown (WhySheet) ----------

async def get_rating_breakdown(match_id: str, player_id: str, at_ball_id: Optional[str] = None) -> Optional[RatingBreakdown]:
    db = get_db()
    q = {"match_id": match_id, "player_id": player_id}
    snap = None
    if at_ball_id:
        snap = await db.ratings_snapshots.find_one({**q, "after_ball_id": at_ball_id}, {"_id": 0})
        if not snap:
            # Fallback: latest snapshot for this player at or before the requested ball's match_seq.
            # We don't know match_seq of an unknown ball_id → just return latest overall.
            snap = await db.ratings_snapshots.find_one(q, {"_id": 0}, sort=[("match_seq", -1)])
    else:
        snap = await db.ratings_snapshots.find_one(q, {"_id": 0}, sort=[("match_seq", -1)])
    if not snap:
        return None

    # Collect ALL components for this player up to the latest match_seq we're showing
    max_seq = int(snap["match_seq"])
    all_snaps = await db.ratings_snapshots.find(
        {"match_id": match_id, "player_id": player_id, "match_seq": {"$lte": max_seq}},
        {"_id": 0, "component": 1, "match_seq": 1},
    ).sort("match_seq", 1).to_list(1000)
    components = [RatingComponent(**s["component"]) for s in all_snaps]

    player_name = snap.get("player_name", player_id)
    return RatingBreakdown(
        player_id=player_id,
        player_name=player_name,
        match_id=match_id,
        after_ball_id=snap.get("after_ball_id"),
        base_rating=5.0,  # engine's neutral baseline (wpa_to_rating(0) = 5.0)
        components=components,
        final_rating=float(snap["final_rating"]),
        delta_from_previous=float(snap.get("delta", 0.0)),
        narrative="",
    )
