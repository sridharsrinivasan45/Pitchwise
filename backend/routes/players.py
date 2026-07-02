"""Player routes — index + profile. Pure data access, no analytics."""
from fastapi import APIRouter, HTTPException, Query
from core.db import get_db
from data.team_aliases import resolve_team

router = APIRouter(prefix="/players", tags=["players"])


def _current_team_short(teams: list[str]) -> str:
    """Take the last-known team (most recent season) as current."""
    if not teams:
        return ""
    return resolve_team(teams[-1])["short"]


@router.get("")
async def list_players(
    search: str = Query(""),
    team: str = Query(""),  # short code
    role: str = Query(""),  # 'batter' | 'bowler' | 'allrounder'
    sort: str = Query("rating"),  # rating | matches | name
    limit: int = Query(60, ge=1, le=300),
    offset: int = Query(0, ge=0),
):
    db = get_db()

    # 1) Aggregate career metrics per player from match_ratings
    match_q: dict = {}
    if role in ("batter", "bowler", "allrounder"):
        # Filter by whether the player has meaningful contributions of this role
        if role == "batter":
            match_q["balls_faced"] = {"$gt": 0}
        elif role == "bowler":
            match_q["balls_bowled"] = {"$gt": 0}
        elif role == "allrounder":
            match_q["balls_faced"] = {"$gt": 0}
            match_q["balls_bowled"] = {"$gt": 0}

    pipeline = [
        {"$match": match_q} if match_q else {"$match": {}},
        {"$group": {
            "_id": "$player_id",
            "player_name": {"$last": "$player_name"},
            "matches": {"$sum": 1},
            "avg_rating": {"$avg": "$overall_rating"},
            "best_rating": {"$max": "$overall_rating"},
            "total_runs": {"$sum": "$runs"},
            "total_wickets": {"$sum": "$wickets"},
            "total_balls_faced": {"$sum": "$balls_faced"},
            "total_balls_bowled": {"$sum": "$balls_bowled"},
        }},
        {"$match": {"matches": {"$gte": 3}}},  # min 3 matches for a career entry
    ]
    if search:
        pipeline.append({"$match": {"player_name": {"$regex": search, "$options": "i"}}})

    if sort == "matches":
        pipeline.append({"$sort": {"matches": -1, "avg_rating": -1}})
    elif sort == "name":
        pipeline.append({"$sort": {"player_name": 1}})
    else:
        pipeline.append({"$sort": {"avg_rating": -1, "matches": -1}})

    total_pipeline = pipeline + [{"$count": "n"}]
    total_docs = await db.match_ratings.aggregate(total_pipeline).to_list(1)
    total = total_docs[0]["n"] if total_docs else 0

    pipeline.append({"$skip": offset})
    pipeline.append({"$limit": limit})
    rows = await db.match_ratings.aggregate(pipeline).to_list(limit)

    # 2) Enrich with team info from players collection
    player_ids = [r["_id"] for r in rows]
    player_docs = {}
    async for p in db.players.find({"player_id": {"$in": player_ids}}, {"_id": 0}):
        player_docs[p["player_id"]] = p

    out = []
    for r in rows:
        p = player_docs.get(r["_id"], {})
        teams = p.get("teams", [])
        current = _current_team_short(teams)
        if team and team != current:
            continue
        bat = int(r["total_balls_faced"])
        bowl = int(r["total_balls_bowled"])
        derived_role = "allrounder" if (bat > 60 and bowl > 60) else \
                       "bowler" if bowl > bat else "batter"
        out.append({
            "player_id": r["_id"],
            "name": r["player_name"],
            "display_name": p.get("display_name") or r["player_name"],
            "team_short": current,
            "team_history": [resolve_team(t)["short"] for t in teams],
            "matches": int(r["matches"]),
            "career_rating": round(float(r["avg_rating"]), 2),
            "best_rating": round(float(r["best_rating"]), 2),
            "runs": int(r["total_runs"]),
            "wickets": int(r["total_wickets"]),
            "role": derived_role,
        })

    return {"players": out, "total": total, "limit": limit, "offset": offset}


@router.get("/{player_id}")
async def get_player_profile(player_id: str):
    db = get_db()
    p = await db.players.find_one({"player_id": player_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Player not found")

    # Career stats
    stats = await db.match_ratings.aggregate([
        {"$match": {"player_id": player_id}},
        {"$group": {
            "_id": None,
            "matches": {"$sum": 1},
            "avg_rating": {"$avg": "$overall_rating"},
            "best_rating": {"$max": "$overall_rating"},
            "avg_batting": {"$avg": "$batting_rating"},
            "avg_bowling": {"$avg": "$bowling_rating"},
            "total_runs": {"$sum": "$runs"},
            "total_wickets": {"$sum": "$wickets"},
            "total_balls_faced": {"$sum": "$balls_faced"},
            "total_balls_bowled": {"$sum": "$balls_bowled"},
        }},
    ]).to_list(1)
    stats = stats[0] if stats else {}

    # Best 5 performances
    best_docs = await db.match_ratings.find(
        {"player_id": player_id}, {"_id": 0}
    ).sort("overall_rating", -1).limit(5).to_list(5)
    best = []
    for b in best_docs:
        m = await db.matches.find_one({"match_id": b["match_id"]},
                                      {"_id": 0, "date": 1, "season": 1, "team_short": 1, "result_summary": 1, "curation_title": 1})
        best.append({
            "match_id": b["match_id"],
            "date": m["date"] if m else "",
            "season": m["season"] if m else "",
            "teams": "-".join(m["team_short"]) if m else "",
            "result_summary": m.get("result_summary") if m else "",
            "curation_title": m.get("curation_title") if m else None,
            "overall_rating": round(float(b["overall_rating"]), 2),
            "batting_rating": round(float(b["batting_rating"]), 2),
            "bowling_rating": round(float(b["bowling_rating"]), 2),
            "runs": int(b["runs"]),
            "wickets": int(b["wickets"]),
            "balls_faced": int(b["balls_faced"]),
        })

    # Rating timeline: overall_rating per match ordered by date
    timeline_docs = await db.match_ratings.aggregate([
        {"$match": {"player_id": player_id}},
        {"$lookup": {"from": "matches", "localField": "match_id", "foreignField": "match_id", "as": "m"}},
        {"$unwind": "$m"},
        {"$project": {"_id": 0, "date": "$m.date", "match_id": 1, "overall_rating": 1, "season": "$m.season"}},
        {"$sort": {"date": 1}},
    ]).to_list(2000)

    # Recent 5 matches
    recent = list(reversed(timeline_docs[-5:])) if timeline_docs else []
    recent_enriched = []
    for r in recent:
        m = await db.matches.find_one({"match_id": r["match_id"]},
                                      {"_id": 0, "team_short": 1, "result_summary": 1})
        recent_enriched.append({
            "match_id": r["match_id"], "date": r["date"], "season": r["season"],
            "teams": "-".join(m["team_short"]) if m else "",
            "result_summary": m.get("result_summary") if m else "",
            "overall_rating": round(float(r["overall_rating"]), 2),
        })

    return {
        "player_id": player_id,
        "name": p.get("cricsheet_name") or p.get("display_name") or player_id,
        "display_name": p.get("display_name") or p.get("cricsheet_name") or player_id,
        "teams": [resolve_team(t)["short"] for t in p.get("teams", [])],
        "team_history_full": [resolve_team(t)["name"] for t in p.get("teams", [])],
        "seasons": p.get("seasons", []),
        "first_seen": p.get("first_seen"),
        "last_seen": p.get("last_seen"),
        "career": {
            "matches": int(stats.get("matches", 0)),
            "avg_rating": round(float(stats.get("avg_rating", 0.0)), 2),
            "best_rating": round(float(stats.get("best_rating", 0.0)), 2),
            "avg_batting": round(float(stats.get("avg_batting", 0.0)), 2),
            "avg_bowling": round(float(stats.get("avg_bowling", 0.0)), 2),
            "total_runs": int(stats.get("total_runs", 0)),
            "total_wickets": int(stats.get("total_wickets", 0)),
            "total_balls_faced": int(stats.get("total_balls_faced", 0)),
            "total_balls_bowled": int(stats.get("total_balls_bowled", 0)),
        },
        "best_performances": best,
        "timeline": [{"date": t["date"], "match_id": t["match_id"], "overall_rating": round(float(t["overall_rating"]), 2), "season": t["season"]} for t in timeline_docs],
        "recent_matches": recent_enriched,
    }
