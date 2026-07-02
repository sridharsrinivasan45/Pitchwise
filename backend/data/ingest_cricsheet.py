"""
Cricsheet → PitchWise ingest pipeline.

Reproducible, idempotent, incremental. Single-command entry point:

    python -m data.ingest_cricsheet --archive /app/data/ipl_json.zip

Behavior contract:
  * Reproducible — running twice on the same archive produces identical DB state.
  * Idempotent   — a match is skipped if its source_hash matches what's stored.
  * Incremental  — --only-new skips any match_id already present; new seasons drop in without full rebuild.

What lands in Mongo:
  * matches           — one doc per match (with source_hash, DLS/tie flags, POM, display aliases)
  * balls             — one doc per delivery in engine's expected shape
                        (legal_ball_num, cum_runs, cum_wickets, target, is_legal, is_wicket, etc.)
  * players           — one doc per registry hex ID (canonical Cricsheet name + display name)

The WPA/ratings/moments/snapshots layer is Stage 3+4, not this file.

The engine methodology is NOT touched — this file only produces its expected inputs.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Bootstrap so this can be run as `python -m data.ingest_cricsheet`
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from core.db import get_db  # noqa: E402
from data.team_aliases import resolve_team  # noqa: E402


# ---------- helpers ----------

# Wickets counted as batting-team wickets_in_hand loss for WPA purposes.
# Following Cricsheet + engine semantics, retired hurt / obstructing the field
# / run out are unusual — we keep them in cum_wickets because they DO end
# that batter's innings (balls consumed against the chase). This matches the
# WPA engine's assumption that wickets_in_hand = 10 - cum_wickets.
BATTER_DISMISSAL_KINDS_ALL = {
    "bowled", "caught", "caught and bowled", "lbw", "stumped",
    "hit wicket", "hit the ball twice", "run out", "retired hurt",
    "retired out", "obstructing the field", "handled the ball", "timed out",
}


def get_phase(over_idx: int) -> str:
    """Same as engine.core.ipl_ratings.get_phase — kept in ingest to avoid import cycles."""
    if over_idx <= 5:
        return "powerplay"
    if over_idx <= 14:
        return "middle"
    return "death"


def file_hash(payload: bytes) -> str:
    return hashlib.sha1(payload).hexdigest()


# ---------- one-match parse ----------

def parse_match(match_id: str, raw: dict) -> dict:
    """
    Convert one Cricsheet match JSON dict into a bundle of docs ready for Mongo.
    Returns:
        {
          "match": <matches doc>,
          "balls": [<ball docs>],
          "player_refs": [ {player_id, cricsheet_name, teams:set, seasons:set, first_seen, last_seen} ],
        }
    """
    info = raw["info"]
    winner = info.get("outcome", {}).get("winner")
    outcome = info.get("outcome", {})
    result_kind = outcome.get("result")  # "tie" | "no result" | "draw" | None (normal)
    method = outcome.get("method")       # "D/L" if DLS applied
    has_dls = bool(method and "D/L" in str(method).upper() or method == "D/L")

    season = str(info.get("season", ""))
    dates = info.get("dates") or []
    date = dates[0] if dates else None
    venue = info.get("venue", "")
    city = info.get("city", "")
    teams_raw = info.get("teams", [])
    pom_names = info.get("player_of_match") or []

    # Registry: name -> hex_id
    registry = info.get("registry", {}).get("people", {}) or {}
    # players[team] -> list of names in the playing XI
    playing = info.get("players", {}) or {}

    def pid(name: str | None) -> str | None:
        if not name:
            return None
        # If registered, use hex ID; otherwise fall back to slug of name (rare)
        return registry.get(name) or f"name:{name}"

    innings_docs = raw.get("innings", [])
    balls: list[dict] = []
    innings_totals: list[int] = []
    innings_teams: list[str] = []
    has_super_over = False

    for inn_idx, inn in enumerate(innings_docs, start=1):
        batting_team = inn.get("team")
        innings_teams.append(batting_team)
        if inn.get("super_over"):
            has_super_over = True
            # Skip super over from balls (WPA engine explicitly excludes innings>=3)
            continue
        # Target on chase innings only
        target = None
        if inn_idx == 2:
            target = inn.get("target", {}).get("runs")

        bowling_team = next((t for t in teams_raw if t != batting_team), None)

        cum_runs = 0
        cum_wickets = 0
        legal_ball_num = 0
        ball_seq = 0  # unique sequence within this innings (includes wides/nb)

        for over_obj in inn.get("overs", []):
            over_num = over_obj["over"]  # 0-indexed
            phase = get_phase(over_num)
            for delivery_pos, b in enumerate(over_obj.get("deliveries", []), start=1):
                ball_seq += 1
                extras = b.get("extras", {}) or {}
                is_wide = "wides" in extras
                is_nb = "noballs" in extras
                is_legal = 0 if (is_wide or is_nb) else 1
                if is_legal:
                    legal_ball_num += 1

                runs_batter = int(b["runs"].get("batter", 0))
                runs_total = int(b["runs"].get("total", 0))
                runs_extras = int(b["runs"].get("extras", 0))

                is_wicket = 0
                dismissed_name: str | None = None
                dismissal_type: str | None = None
                for wkt in b.get("wickets") or []:
                    kind = wkt.get("kind")
                    if kind in BATTER_DISMISSAL_KINDS_ALL:
                        is_wicket = 1
                        dismissed_name = wkt.get("player_out")
                        dismissal_type = kind
                cum_runs += runs_total
                cum_wickets += is_wicket

                ball_uid = f"{match_id}-i{inn_idx}-{ball_seq:03d}"
                balls.append({
                    # Unique identity
                    "ball_uid": ball_uid,
                    "match_id": match_id,
                    "innings": inn_idx,
                    "over": over_num,
                    "ball_in_over": delivery_pos,
                    "innings_seq": ball_seq,

                    # Players (canonical IDs + cricsheet names for engine)
                    "batter": b.get("batter"),
                    "bowler": b.get("bowler"),
                    "non_striker": b.get("non_striker"),
                    "batter_id": pid(b.get("batter")),
                    "bowler_id": pid(b.get("bowler")),
                    "non_striker_id": pid(b.get("non_striker")),

                    # Outcome
                    "runs_batter": runs_batter,
                    "runs_total": runs_total,
                    "runs_extras": runs_extras,
                    "extras": extras,
                    "is_wicket": is_wicket,
                    "is_legal": is_legal,
                    "dismissed_player_id": pid(dismissed_name),
                    "dismissed_player": dismissed_name,
                    "dismissal_type": dismissal_type,

                    # Engine-required aggregate context
                    "cum_runs": cum_runs,
                    "cum_wickets": cum_wickets,
                    "target": target,
                    "legal_ball_num": legal_ball_num,

                    # Meta
                    "phase": phase,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "season": season,
                    "winner": winner,
                })
        innings_totals.append(cum_runs)

    # Result normalization
    if result_kind == "tie":
        result_type = "tie"
    elif result_kind in ("no result", "abandoned"):
        result_type = "no_result"
    elif has_dls:
        result_type = "dls"
    else:
        result_type = "normal"

    # Result summary string
    result_summary = None
    if winner:
        by = outcome.get("by", {}) or {}
        if "wickets" in by:
            result_summary = f"{resolve_team(winner)['short']} won by {by['wickets']} wickets"
        elif "runs" in by:
            result_summary = f"{resolve_team(winner)['short']} won by {by['runs']} runs"
        else:
            result_summary = f"{resolve_team(winner)['short']} won"
    elif result_type == "tie":
        result_summary = "Match tied"
    elif result_type == "no_result":
        result_summary = "No result"

    # Score string: "TEAM1 t1 - TEAM2 t2 (their overs)"
    # Only if we have at least first innings scored
    final_score = None
    if innings_totals and innings_teams:
        parts = []
        for team, tot in zip(innings_teams[: len(innings_totals)], innings_totals):
            parts.append(f"{resolve_team(team)['short']} {tot}")
        final_score = " — ".join(parts)

    match_doc = {
        "match_id": match_id,
        "season": season,
        "date": date,
        "teams": teams_raw,
        "team_short": [resolve_team(t)["short"] for t in teams_raw],
        "team_display": [resolve_team(t)["name"] for t in teams_raw],
        "batting_first": innings_teams[0] if innings_teams else None,
        "winner": winner,
        "outcome": {
            "winner": winner,
            "by": outcome.get("by", {}),
            "result": result_type,
            "method": method,
        },
        "venue": venue,
        "city": city,
        "player_of_match_names": pom_names,
        "player_of_match_ids": [pid(n) for n in pom_names],
        "balls_per_over": info.get("balls_per_over", 6),
        "first_innings_total": innings_totals[0] if innings_totals else None,
        "second_innings_total": innings_totals[1] if len(innings_totals) > 1 else None,
        "target": next((b["target"] for b in balls if b["innings"] == 2 and b["target"]), None),
        "has_dls": has_dls,
        "has_super_over": has_super_over,
        "result_summary": result_summary,
        "final_score": final_score,
        "format": info.get("match_type", "T20"),
        "status": "time_machine",
        "ball_count": len(balls),
    }

    # Player refs — build from registry for all XI + officials, plus anyone appearing in balls
    player_refs: dict[str, dict] = {}
    for team, names in playing.items():
        for name in names:
            hid = registry.get(name)
            if not hid:
                continue
            player_refs.setdefault(hid, {
                "player_id": hid,
                "cricsheet_name": name,
                "teams": set(),
                "seasons": set(),
                "first_seen": date,
                "last_seen": date,
            })["teams"].add(resolve_team(team)["name"])
            player_refs[hid]["seasons"].add(season)
            player_refs[hid]["last_seen"] = date
    # Also cover anyone with balls but not in playing dict (shouldn't happen, but safe)
    for b in balls:
        for name, pid_ in [(b["batter"], b["batter_id"]), (b["bowler"], b["bowler_id"])]:
            if not pid_ or pid_.startswith("name:"):
                continue
            if pid_ not in player_refs:
                player_refs[pid_] = {
                    "player_id": pid_, "cricsheet_name": name,
                    "teams": {resolve_team(b["batting_team"] if pid_ == b["batter_id"] else b["bowling_team"])["name"]},
                    "seasons": {season},
                    "first_seen": date, "last_seen": date,
                }

    return {
        "match": match_doc,
        "balls": balls,
        "player_refs": list(player_refs.values()),
    }


# ---------- Mongo I/O ----------

async def _ensure_indexes(db):
    await db.matches.create_index([("match_id", 1)], unique=True)
    await db.matches.create_index([("season", 1), ("date", -1)])
    await db.matches.create_index([("featured", 1)])
    await db.balls.create_index([("match_id", 1), ("innings", 1), ("innings_seq", 1)])
    await db.balls.create_index([("ball_uid", 1)], unique=True)
    await db.balls.create_index([("batter_id", 1)])
    await db.balls.create_index([("bowler_id", 1)])
    await db.players.create_index([("player_id", 1)], unique=True)


async def _upsert_match(db, parsed: dict, source_hash: str) -> None:
    match_id = parsed["match"]["match_id"]
    # Wipe old balls, then insert fresh. Cheap for a single match (~250 docs).
    await db.balls.delete_many({"match_id": match_id})
    if parsed["balls"]:
        await db.balls.insert_many(parsed["balls"])
    # Match doc with source_hash + ingested_at
    doc = dict(parsed["match"])
    doc["source_hash"] = source_hash
    doc["ingested_at"] = datetime.now(timezone.utc).isoformat()
    await db.matches.update_one(
        {"match_id": match_id}, {"$set": doc}, upsert=True,
    )
    # Player refs — union teams/seasons per player
    for ref in parsed["player_refs"]:
        await db.players.update_one(
            {"player_id": ref["player_id"]},
            {
                "$set": {
                    "cricsheet_name": ref["cricsheet_name"],
                    "display_name": ref["cricsheet_name"],  # editable later
                    "last_seen": ref["last_seen"],
                },
                "$setOnInsert": {"first_seen": ref["first_seen"]},
                "$addToSet": {
                    "teams": {"$each": sorted(ref["teams"])},
                    "seasons": {"$each": sorted(ref["seasons"])},
                },
            },
            upsert=True,
        )


# ---------- Main ingest ----------

async def ingest(
    archive_path: str,
    only_new: bool = False,
    only_hash_changed: bool = True,
    since: str | None = None,
    limit: int | None = None,
) -> dict:
    """
    Ingest all matches from a Cricsheet ipl_json.zip archive.

    Modes:
        only_new=True         → skip any match_id already present, regardless of hash
        only_hash_changed=True→ (default) reingest a match iff its source hash changed
        since='YYYY-MM-DD'    → only consider files whose match date >= threshold
        limit=N               → process at most N matches (for smoke tests)

    Returns a summary dict.
    """
    db = get_db()
    await _ensure_indexes(db)

    t0 = time.time()
    stats = {
        "considered": 0, "ingested": 0, "skipped_hash_match": 0,
        "skipped_already_present": 0, "skipped_since": 0,
        "errors": 0, "error_ids": [],
    }

    # Preload known hashes for idempotency
    known: dict[str, str] = {}
    async for m in db.matches.find({}, {"_id": 0, "match_id": 1, "source_hash": 1}):
        known[m["match_id"]] = m.get("source_hash") or ""

    with tempfile.TemporaryDirectory():
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = [n for n in zf.namelist() if n.endswith(".json") and not n.endswith("/README.txt")]
            names.sort()  # deterministic order
            if limit:
                names = names[:limit]

            for name in names:
                match_id = os.path.splitext(os.path.basename(name))[0]
                try:
                    payload = zf.read(name)
                    h = file_hash(payload)

                    stats["considered"] += 1
                    if only_new and match_id in known:
                        stats["skipped_already_present"] += 1
                        continue
                    if only_hash_changed and known.get(match_id) == h:
                        stats["skipped_hash_match"] += 1
                        continue

                    raw = json.loads(payload)
                    # since filter
                    if since:
                        dates = raw.get("info", {}).get("dates") or []
                        if not dates or str(dates[0]) < since:
                            stats["skipped_since"] += 1
                            continue

                    parsed = parse_match(match_id, raw)
                    await _upsert_match(db, parsed, source_hash=h)
                    stats["ingested"] += 1

                    if stats["ingested"] % 100 == 0:
                        print(f"  ...ingested {stats['ingested']} matches so far")

                except Exception as e:  # pragma: no cover
                    stats["errors"] += 1
                    stats["error_ids"].append((match_id, str(e)[:120]))
                    if stats["errors"] <= 5:
                        print(f"  ! error on {match_id}: {e}")

    stats["seconds"] = round(time.time() - t0, 2)
    return stats


async def mark_featured(featured_slugs: dict[str, dict]) -> int:
    """
    Curate Time Machine matches by match_id → {slug, title, hook}.
    Idempotent: any match not in the dict is un-featured.
    """
    db = get_db()
    await db.matches.update_many({}, {"$set": {"featured": False, "curation_slug": None, "curation_title": None, "curation_hook": None}})
    for mid, meta in featured_slugs.items():
        await db.matches.update_one(
            {"match_id": mid},
            {"$set": {
                "featured": True,
                "curation_slug": meta["slug"],
                "curation_title": meta["title"],
                "curation_hook": meta["hook"],
                "status": "time_machine",
            }},
        )
    return len(featured_slugs)


# Default Time Machine curation — user can override later
FEATURED = {
    "1359487": {
        "slug": "rinku-5-sixes",
        "title": "Rinku's 5 Sixes",
        "hook": "KKR needed 29 off the last over. Watch every rating shift, ball by ball.",
    },
}


def main():
    p = argparse.ArgumentParser(description="Ingest Cricsheet IPL archive into PitchWise Mongo.")
    p.add_argument("--archive", default="/app/data/ipl_json.zip", help="Path to ipl_json.zip")
    p.add_argument("--only-new", action="store_true", help="Skip any match_id already in DB")
    p.add_argument("--force", action="store_true", help="Reingest even when hashes match")
    p.add_argument("--since", default=None, help="Only ingest matches on/after YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=None, help="Process at most N matches")
    p.add_argument("--wipe-old-seed", action="store_true", help="Delete pre-Cricsheet seed match 'kkr-gt-2023-04-09' + its rows")
    p.add_argument("--no-featured", action="store_true", help="Skip setting Time Machine curation")
    args = p.parse_args()

    async def _run():
        if args.wipe_old_seed:
            db = get_db()
            for c in ("matches", "balls", "ratings_snapshots", "moments"):
                r = await db[c].delete_many({"match_id": "kkr-gt-2023-04-09"})
                print(f"  wiped {r.deleted_count} from {c} (old placeholder seed)")

        print(f"[ingest] archive={args.archive}  since={args.since}  only_new={args.only_new}  force={args.force}  limit={args.limit}")
        stats = await ingest(
            archive_path=args.archive,
            only_new=args.only_new,
            only_hash_changed=not args.force,
            since=args.since,
            limit=args.limit,
        )
        print()
        print("=== INGEST SUMMARY ===")
        for k, v in stats.items():
            if k == "error_ids":
                continue
            print(f"  {k:>28}: {v}")
        if stats["errors"]:
            print(f"  first errors: {stats['error_ids'][:5]}")

        if not args.no_featured:
            n = await mark_featured(FEATURED)
            print(f"  curated {n} featured Time Machine matches")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
