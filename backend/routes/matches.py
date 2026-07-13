"""Match routes with search / filter / sort + facets."""
from fastapi import APIRouter, HTTPException, Query
from engine import adapter
from core.db import get_db
from data.team_aliases import resolve_team

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
async def list_matches(
    featured: bool = Query(False),
    search: str = Query(""),
    season: str = Query(""),
    team: str = Query(""),  # short code like "KKR"
    sort: str = Query("newest"),  # newest | oldest | impact
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    q: dict = {}
    if featured:
        q["featured"] = True
    if season:
        q["season"] = season
    if team:
        # match_short list has team code
        q["team_short"] = team
    if search:
        s = {"$regex": search, "$options": "i"}
        q["$or"] = [
            {"venue": s}, {"city": s}, {"teams": s},
            {"curation_title": s}, {"result_summary": s},
        ]

    sort_key = [("date", -1)] if sort == "newest" else \
               [("date", 1)] if sort == "oldest" else \
               [("total_impact", -1)] if sort == "impact" else [("date", -1)]

    total = await db.matches.count_documents(q)
    proj = {"_id": 0}
    docs = await db.matches.find(q, proj).sort(sort_key).skip(offset).limit(limit).to_list(limit)

    # Left-join cached verdicts (narrations). No forced compute — cards degrade gracefully.
    match_ids = [d["match_id"] for d in docs]
    narration_docs = {}
    if match_ids:
        async for n in db.narrations.find(
            {"match_id": {"$in": match_ids}},
            {"_id": 0, "match_id": 1, "payload.verdict.polished": 1, "payload.verdict.sentence": 1, "payload.verdict.archetype": 1},
        ):
            v = ((n.get("payload") or {}).get("verdict") or {})
            narration_docs[n["match_id"]] = {
                "verdict": v.get("polished") or v.get("sentence"),
                "archetype": v.get("archetype"),
            }

    def _summary(d: dict) -> dict:
        teams_raw = d.get("teams", [])
        nn = narration_docs.get(d["match_id"], {})
        return {
            "match_id": d["match_id"],
            "season": d.get("season", ""),
            "date": d.get("date", ""),
            "teams": [resolve_team(t)["name"] for t in teams_raw],
            "team_short": [resolve_team(t)["short"] for t in teams_raw],
            "venue": d.get("venue", ""),
            "city": d.get("city", ""),
            "status": d.get("status", "time_machine"),
            "featured": bool(d.get("featured", False)),
            "curation_slug": d.get("curation_slug"),
            "curation_title": d.get("curation_title"),
            "curation_hook": d.get("curation_hook"),
            "result_summary": d.get("result_summary"),
            "final_score": d.get("final_score"),
            "ball_count": int(d.get("ball_count", 0)),
            "total_impact": float(d.get("total_impact", 0.0)),
            "has_dls": bool(d.get("has_dls", False)),
            "has_super_over": bool(d.get("has_super_over", False)),
            "verdict": nn.get("verdict"),
            "archetype": nn.get("archetype"),
        }

    return {"matches": [_summary(d) for d in docs], "total": total}


@router.get("/facets")
async def get_facets():
    """Distinct seasons + team codes for filter dropdowns."""
    db = get_db()
    seasons = await db.matches.distinct("season")
    seasons = sorted([s for s in seasons if s], reverse=True)
    team_shorts = await db.matches.distinct("team_short")
    team_shorts = sorted({t for t in team_shorts if t})
    # Include venues top-N
    venues = await db.matches.distinct("venue")
    venues = sorted([v for v in venues if v])
    return {"seasons": seasons, "teams": team_shorts, "venues": venues[:50]}


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


@router.get("/{match_id}/skip-to-death")
async def get_skip_to_death(match_id: str):
    """Return the ball sequence index for start of over 20 in the chase (innings 2)."""
    db = get_db()
    balls = await db.balls.find(
        {"match_id": match_id}, {"_id": 0, "innings": 1, "over": 1}
    ).sort([("innings", 1), ("over", 1), ("ball_in_over", 1)]).to_list(500)
    if not balls:
        raise HTTPException(404, "Match not found")
    # Find first index where innings==2 and over==19; fall back to 80% of total
    idx = next((i for i, b in enumerate(balls) if b["innings"] == 2 and b["over"] >= 18), None)
    if idx is None:
        idx = int(len(balls) * 0.85)
    return {"match_id": match_id, "skip_to_ball": idx, "total_balls": len(balls)}
