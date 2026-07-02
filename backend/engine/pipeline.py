"""
Materializer — runs the uploaded analytics engine over the ingested balls
and persists the derived outputs back to Mongo. The adapter reads these
persisted collections; it does NOT recompute analytics.

The engine (backend/engine/core/) is called UNCHANGED. This file only:
  1. Loads events from Mongo into a DataFrame in the engine's expected schema
  2. Invokes engine.core.wpa_engine.* functions verbatim
  3. Invokes engine.core.ratings_from_wpa.* verbatim
  4. Persists results to derived collections
  5. Computes running rating snapshots by calling engine's wpa_to_rating on
     cumulative WPA (NOT duplicating analytics — just applying engine's own
     function ball-by-ball, which the engine itself does not persist)

Collections written:
  * wpa_ball_events   — every ball enriched with wpa fields
  * match_ratings     — final per-player per-match rating (engine output)
  * ratings_snapshots — running per-player-per-ball rating trajectory
  * moments           — top |wpa| moments per match, classified for UI
"""
from __future__ import annotations
import argparse
import asyncio
import pickle
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(BACKEND / ".env")

import pandas as pd  # noqa: E402
from core.db import get_db  # noqa: E402
from engine.core.wpa_engine import (  # noqa: E402
    add_wpa_first_innings, add_wpa_second_innings, compute_opposition_adjustment,
)
from engine.core.ratings_from_wpa import build_match_ratings, wpa_to_rating  # noqa: E402

ARTIFACTS = BACKEND / "engine" / "artifacts"
MODEL_PATH = ARTIFACTS / "wp_model.pkl"

ENGINE_COLS = [
    "match_id", "innings", "over", "ball_in_over", "batter", "bowler",
    "runs_batter", "runs_total", "is_wicket", "is_legal",
    "cum_runs", "cum_wickets", "target", "legal_ball_num",
    "season", "batting_team", "winner",
]
UID_COLS = ["match_id", "innings", "over", "ball_in_over"]


def _load_model():
    with MODEL_PATH.open("rb") as f:
        d = pickle.load(f)
    return d["model"], d["feature_cols"]


async def _load_balls_df(match_ids: list[str] | None) -> pd.DataFrame:
    db = get_db()
    q = {"match_id": {"$in": match_ids}} if match_ids else {}
    proj = {c: 1 for c in ENGINE_COLS + ["ball_uid", "batter_id", "bowler_id", "phase", "dismissed_player_id", "dismissal_type"]}
    proj["_id"] = 0
    rows = await db.balls.find(q, proj).to_list(400000)
    return pd.DataFrame(rows)


def _run_engine_wpa(df: pd.DataFrame, model, feature_cols) -> pd.DataFrame:
    """Runs engine's WPA pipeline on the given events DataFrame. Verbatim."""
    events = df[ENGINE_COLS].copy().convert_dtypes(dtype_backend="numpy_nullable")
    events = events[events["innings"].isin([1, 2])].copy()

    second = events[(events["innings"] == 2) & events["target"].notna()].copy()
    first = events[events["innings"] == 1].copy()

    wpa_2nd = add_wpa_second_innings(second, model, feature_cols)
    wpa_1st = add_wpa_first_innings(first, model, feature_cols)
    full = pd.concat([wpa_1st, wpa_2nd], ignore_index=True)

    # Opposition adjustment (Phase 3 — verbatim engine call)
    opp = compute_opposition_adjustment(events)
    full = full.merge(opp[["season", "bowler", "strength_multiplier"]],
                      on=["season", "bowler"], how="left")
    full["strength_multiplier"] = full["strength_multiplier"].fillna(1.0)
    full["batter_wpa"] = full["wpa"]
    full["batter_wpa_adjusted"] = full["wpa"] * full["strength_multiplier"]
    full["bowler_wpa"] = -full["wpa"]
    return full


def _classify_reason(row: pd.Series, role: str) -> str:
    """Presentation-only mapping. NOT analytics — just labels the UI needs."""
    if role == "batter":
        if bool(row["is_wicket"]):
            return "WICKET_KEY_MOMENT"
        rb = int(row["runs_batter"])
        if rb == 6:
            return "PRESSURE_BOUNDARY"
        if rb == 4:
            return "BOUNDARY"
        if rb == 0:
            return "DOT_UNDER_PRESSURE"
        return "ROTATE_STRIKE"
    # bowler
    if bool(row["is_wicket"]):
        return "WICKET_KEY_MOMENT"
    rt = int(row["runs_total"])
    if rt == 0:
        return "DOT_UNDER_PRESSURE"
    if rt >= 4:
        return "CONCEDED_BOUNDARY"
    return "CONCEDED_MINOR"


async def _persist_wpa_events(wpa: pd.DataFrame):
    """Upsert the WPA per-ball fields onto the existing balls docs."""
    db = get_db()
    # For efficiency, use bulk_write
    from pymongo import UpdateOne
    ops = []
    for r in wpa.itertuples(index=False):
        filt = {"match_id": r.match_id, "innings": int(r.innings),
                "over": int(r.over), "ball_in_over": int(r.ball_in_over)}
        upd = {"$set": {
            "wp_before": float(r.win_prob_before),
            "wp_after": float(r.win_prob_after),
            "wpa": float(r.wpa),
            "batter_wpa_adjusted": float(r.batter_wpa_adjusted),
            "bowler_wpa": float(r.bowler_wpa),
            "strength_multiplier": float(r.strength_multiplier),
            "innings_type": str(r.innings_type),
        }}
        ops.append(UpdateOne(filt, upd))
        if len(ops) >= 2000:
            await db.balls.bulk_write(ops, ordered=False)
            ops.clear()
    if ops:
        await db.balls.bulk_write(ops, ordered=False)


async def _persist_match_ratings(match_ratings: pd.DataFrame, wpa: pd.DataFrame):
    """One doc per (match_id, player) with final rating."""
    db = get_db()
    from pymongo import UpdateOne
    # Batch player_id lookup by cricsheet_name
    names = match_ratings["player"].astype(str).unique().tolist()
    name_to_id: dict[str, str] = {}
    async for p in db.players.find(
        {"cricsheet_name": {"$in": names}},
        {"_id": 0, "player_id": 1, "cricsheet_name": 1},
    ):
        name_to_id[p["cricsheet_name"]] = p["player_id"]
    ops = []
    await db.match_ratings.delete_many({"match_id": {"$in": match_ratings["match_id"].unique().tolist()}})
    for r in match_ratings.itertuples(index=False):
        doc = {
            "match_id": str(r.match_id),
            "player_name": str(r.player),
            "player_id": name_to_id.get(str(r.player), f"name:{r.player}"),
            "runs": int(r.runs), "balls_faced": int(r.balls_faced),
            "batting_wpa": float(r.batting_wpa), "batting_rating": float(r.batting_rating),
            "wickets": int(r.wickets), "balls_bowled": int(r.balls_bowled),
            "bowling_wpa": float(r.bowling_wpa), "bowling_rating": float(r.bowling_rating),
            "total_wpa": float(r.total_wpa), "overall_rating": float(r.overall_rating),
        }
        ops.append(UpdateOne({"match_id": doc["match_id"], "player_id": doc["player_id"]},
                             {"$set": doc}, upsert=True))
        if len(ops) >= 2000:
            await db.match_ratings.bulk_write(ops, ordered=False)
            ops.clear()
    if ops:
        await db.match_ratings.bulk_write(ops, ordered=False)


async def _persist_snapshots_and_moments(wpa: pd.DataFrame):
    """
    Rolling rating snapshots + moments. Both derived by APPLYING the engine's
    own wpa_to_rating function to per-player cumulative WPA — not redefining it.
    """
    db = get_db()

    # ─── SNAPSHOTS ─────────────────────────────────────────────
    # For each (match_id, player), a running snapshot per ball they were involved in.
    # Rating at ball k = wpa_to_rating( cumulative WPA up to k )  ← engine's function
    wpa = wpa.sort_values(["match_id", "innings", "legal_ball_num"]).reset_index(drop=True)
    # Compose a stable ball_uid to store snapshot linkage
    wpa["ball_uid"] = (
        wpa["match_id"].astype(str) + "-i" + wpa["innings"].astype(int).astype(str) +
        "-o" + wpa["over"].astype(int).astype(str) + "." + wpa["ball_in_over"].astype(int).astype(str)
    )
    # Sequence within a match, across both innings
    wpa["match_seq"] = wpa.groupby("match_id").cumcount()

    snapshots: list[dict] = []
    matches_touched = wpa["match_id"].unique().tolist()

    for (match_id, player), grp in wpa.groupby(["match_id", "batter"]):
        grp = grp.sort_values("match_seq")
        cum = 0.0
        prev_rating = 5.0
        for r in grp.itertuples(index=False):
            cum += float(r.batter_wpa_adjusted)
            rating = float(wpa_to_rating(cum, scale=0.15))
            reason = _classify_reason(pd.Series({"is_wicket": r.is_wicket, "runs_batter": r.runs_batter, "runs_total": r.runs_total}), "batter")
            component = {
                "label": f"{_component_label(reason)} (O{int(r.over)+1}.{int(r.ball_in_over)})",
                "weight": round(rating - prev_rating, 4),  # in rating-delta space
                "wpa": float(r.batter_wpa_adjusted),
                "ball_id": r.ball_uid,
                "reason_code": reason,
                "phase": _phase_for(int(r.over)),
            }
            snapshots.append({
                "match_id": str(match_id),
                "player_name": str(player),
                "role": "batter",
                "after_ball_id": r.ball_uid,
                "match_seq": int(r.match_seq),
                "cum_wpa": round(cum, 6),
                "final_rating": round(rating, 2),
                "delta": round(rating - prev_rating, 3),
                "component": component,
            })
            prev_rating = rating

    for (match_id, player), grp in wpa.groupby(["match_id", "bowler"]):
        grp = grp.sort_values("match_seq")
        cum = 0.0
        prev_rating = 5.0
        for r in grp.itertuples(index=False):
            cum += float(r.bowler_wpa)
            rating = float(wpa_to_rating(cum, scale=0.15))
            reason = _classify_reason(pd.Series({"is_wicket": r.is_wicket, "runs_batter": r.runs_batter, "runs_total": r.runs_total}), "bowler")
            component = {
                "label": f"{_component_label(reason)} (O{int(r.over)+1}.{int(r.ball_in_over)})",
                "weight": round(rating - prev_rating, 4),
                "wpa": float(r.bowler_wpa),
                "ball_id": r.ball_uid,
                "reason_code": reason,
                "phase": _phase_for(int(r.over)),
            }
            snapshots.append({
                "match_id": str(match_id),
                "player_name": str(player),
                "role": "bowler",
                "after_ball_id": r.ball_uid,
                "match_seq": int(r.match_seq),
                "cum_wpa": round(cum, 6),
                "final_rating": round(rating, 2),
                "delta": round(rating - prev_rating, 3),
                "component": component,
            })
            prev_rating = rating

    # Attach player_id via batch lookup against the players collection
    name_to_id: dict[str, str] = {}
    all_names = {s["player_name"] for s in snapshots}
    if all_names:
        async for p in db.players.find(
            {"cricsheet_name": {"$in": list(all_names)}},
            {"_id": 0, "player_id": 1, "cricsheet_name": 1},
        ):
            name_to_id[p["cricsheet_name"]] = p["player_id"]
    for s in snapshots:
        s["player_id"] = name_to_id.get(s["player_name"], f"name:{s['player_name']}")

    await db.ratings_snapshots.delete_many({"match_id": {"$in": matches_touched}})
    if snapshots:
        # Insert in chunks
        for i in range(0, len(snapshots), 5000):
            await db.ratings_snapshots.insert_many(snapshots[i:i+5000], ordered=False)

    # ─── MOMENTS ───────────────────────────────────────────────
    # Rank by |wpa|. Presentation-only classification into UI types.
    # Reuse name_to_id populated above
    await db.moments.delete_many({"match_id": {"$in": matches_touched}})
    moments: list[dict] = []
    for match_id, grp in wpa.groupby("match_id"):
        grp = grp.copy()
        grp["abs_wpa"] = grp["wpa"].abs()
        # Top 12 by abs wpa
        top = grp.sort_values("abs_wpa", ascending=False).head(12)
        for r in top.itertuples(index=False):
            is_wicket = bool(r.is_wicket)
            is_six = int(r.runs_batter) == 6
            is_death = int(r.over) >= 15
            if is_wicket:
                mtype = "wicket_key"
                narrative = f"Wicket in O{int(r.over)+1}.{int(r.ball_in_over)} — WPA {r.wpa:+.3f}."
            elif is_six and is_death:
                mtype = "match_turning_point"
                narrative = f"Six under pressure at O{int(r.over)+1}.{int(r.ball_in_over)} — WPA {r.wpa:+.3f}."
            elif is_six:
                mtype = "boundary_streak"
                narrative = f"Six at O{int(r.over)+1}.{int(r.ball_in_over)} — WPA {r.wpa:+.3f}."
            else:
                mtype = "milestone"
                narrative = f"Turning ball at O{int(r.over)+1}.{int(r.ball_in_over)} — WPA {r.wpa:+.3f}."
            moments.append({
                "match_id": str(match_id), "ball_id": r.ball_uid,
                "type": mtype,
                "impact_score": round(abs(float(r.wpa)) * 20, 2),  # display scaling only
                "narrative": narrative,
                "over": int(r.over), "ball": int(r.ball_in_over),
                "sequence": int(r.match_seq),
                "batter_id": name_to_id.get(str(r.batter), f"name:{r.batter}"),
                "bowler_id": name_to_id.get(str(r.bowler), f"name:{r.bowler}"),
            })
    if moments:
        await db.moments.insert_many(moments, ordered=False)


def _phase_for(over_idx: int) -> str:
    if over_idx <= 5:
        return "powerplay"
    if over_idx <= 14:
        return "middle"
    return "death"


def _component_label(reason: str) -> str:
    return {
        "PRESSURE_BOUNDARY": "Six under pressure",
        "BOUNDARY": "Boundary",
        "DOT_UNDER_PRESSURE": "Dot ball",
        "WICKET_KEY_MOMENT": "Wicket",
        "CONCEDED_BOUNDARY": "Conceded boundary",
        "CONCEDED_MINOR": "Conceded runs",
        "ROTATE_STRIKE": "Kept strike moving",
    }.get(reason, reason)


async def build_all_derived(match_ids: list[str] | None = None):
    t0 = time.time()
    print(f"[pipeline] loading model {MODEL_PATH}")
    model, feature_cols = _load_model()

    print("[pipeline] loading balls...")
    df = await _load_balls_df(match_ids)
    if df.empty:
        print("[pipeline] no balls found — abort")
        return

    if match_ids is None:
        # Full rebuild uses ALL balls for correct opposition adjustment (season economy)
        pass
    print(f"[pipeline] loaded {len(df)} balls across {df['match_id'].nunique()} matches")

    print("[pipeline] running WPA engine (unchanged methodology)...")
    wpa = _run_engine_wpa(df, model, feature_cols)
    print(f"[pipeline] WPA rows: {len(wpa)}")

    print("[pipeline] persisting WPA fields onto balls...")
    await _persist_wpa_events(wpa)

    print("[pipeline] engine.build_match_ratings ...")
    match_ratings = build_match_ratings(wpa)
    print(f"[pipeline] match_ratings rows: {len(match_ratings)}")
    await _persist_match_ratings(match_ratings, wpa)

    print("[pipeline] snapshots + moments ...")
    await _persist_snapshots_and_moments(wpa)

    print(f"[pipeline] done in {round(time.time() - t0, 2)}s")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--match", action="append", help="Limit to specific match_id(s). Default: all.")
    args = p.parse_args()
    asyncio.run(build_all_derived(match_ids=args.match))


if __name__ == "__main__":
    main()
