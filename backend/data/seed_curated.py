"""
Curated seed data for the hero Time Machine match:
KKR vs GT, IPL 2023, April 9 — the Rinku Singh 5-sixes finish.

This seed hand-crafts the KKR chase (2nd innings) with realistic ball-by-ball
runs and player attribution, and hand-encodes the crucial 20th over EXACTLY
as it happened: 6, 6, 6, 6, 6 by Rinku Singh off Yash Dayal.

Ratings, moments, momentum are computed here from ball data using a compact
placeholder formula. When the real Python impact engine drops in
(backend/engine/core/), the adapter is rewired to call it and this file
becomes a data-only import layer.
"""
from __future__ import annotations
import asyncio
import random
from datetime import datetime, timezone
from core.db import get_db


MATCH_ID = "kkr-gt-2023-04-09"

# --- Players (KKR chase-relevant) ---
PLAYERS = [
    # KKR
    {"player_id": "narine",   "name": "Sunil Narine",     "role": "batter",  "current_team": "KKR"},
    {"player_id": "gurbaz",   "name": "Rahmanullah Gurbaz","role": "keeper",  "current_team": "KKR"},
    {"player_id": "venkatesh","name": "Venkatesh Iyer",   "role": "batter",  "current_team": "KKR"},
    {"player_id": "nitish",   "name": "Nitish Rana",      "role": "batter",  "current_team": "KKR"},
    {"player_id": "russell",  "name": "Andre Russell",    "role": "allrounder","current_team": "KKR"},
    {"player_id": "rinku",    "name": "Rinku Singh",      "role": "batter",  "current_team": "KKR"},
    {"player_id": "shardul",  "name": "Shardul Thakur",   "role": "allrounder","current_team": "KKR"},
    # GT bowlers
    {"player_id": "mohit",    "name": "Mohit Sharma",     "role": "bowler",  "current_team": "GT"},
    {"player_id": "rashid",   "name": "Rashid Khan",      "role": "bowler",  "current_team": "GT"},
    {"player_id": "noor",     "name": "Noor Ahmad",       "role": "bowler",  "current_team": "GT"},
    {"player_id": "hardik",   "name": "Hardik Pandya",    "role": "allrounder","current_team": "GT"},
    {"player_id": "alzarri",  "name": "Alzarri Joseph",   "role": "bowler",  "current_team": "GT"},
    {"player_id": "yash",     "name": "Yash Dayal",       "role": "bowler",  "current_team": "GT"},
]

# Batting order for the KKR chase
BATTING_ORDER = ["narine", "gurbaz", "venkatesh", "nitish", "russell", "rinku", "shardul"]

# ---------- Ball generation ----------

def _phase(over: int) -> str:
    if over < 6:
        return "powerplay"
    if over < 15:
        return "middle"
    return "death"


def _pressure(over: int, req_rate: float, wickets: int) -> float:
    base = 3.5 + (over / 20) * 3.0 + max(0.0, (req_rate - 8.0)) * 0.6 + wickets * 0.4
    return round(min(9.9, max(1.0, base)), 2)


def _difficulty(bowler_id: str, phase: str) -> float:
    weight = {"rashid": 8.4, "noor": 7.8, "mohit": 7.0, "hardik": 6.5, "alzarri": 6.8, "yash": 6.2}.get(bowler_id, 6.0)
    if phase == "powerplay":
        weight -= 0.5
    if phase == "death":
        weight += 0.3
    return round(min(9.9, weight), 2)


def _make_ball(match_id, innings, over, ball_num, batter, bowler, runs, is_wicket,
               dismissed, extras, phase, wp_before, wp_after, target=205, score=0, wickets=0):
    ball_id = f"{match_id}-i{innings}-{over:02d}.{ball_num}"
    p_index = _pressure(over, req_rate=max(0.0, ((target - score) / max(0.01, (20 - over - ball_num/6)))), wickets=wickets)
    diff = _difficulty(bowler, phase)
    dismissal_type = None
    if is_wicket:
        dismissal_type = random.choice(["caught", "bowled", "lbw", "caught & bowled"])
    # Impact deltas: heavier for boundaries & wickets weighted by pressure
    if is_wicket:
        b_delta = -1.8 - p_index * 0.08
        bwl_delta = 0.9 + p_index * 0.08
    else:
        b_delta = (runs * 0.12) + (0.15 if runs == 6 else 0) + (p_index / 10) * (runs / 6)
        bwl_delta = -(runs * 0.06) + (0.05 if runs == 0 else 0)
    commentary_map = {
        6: "SIX. Lofted over the boundary.",
        4: "FOUR. Beautifully placed.",
        1: "Pushed into the gap for a single.",
        2: "Well run, two.",
        3: "Sprinted through for three.",
        0: "Defended off the front foot.",
    }
    commentary = commentary_map.get(runs, f"{runs} runs.")
    if is_wicket:
        commentary = f"WICKET. {dismissal_type}."
    return {
        "ball_id": ball_id,
        "match_id": match_id,
        "innings": innings,
        "over": over,
        "ball": ball_num,
        "batter_id": batter,
        "bowler_id": bowler,
        "non_striker_id": None,
        "runs_batter": runs if not extras else 0,
        "runs_extras": extras,
        "runs_total": runs + extras,
        "is_wicket": is_wicket,
        "dismissal_type": dismissal_type,
        "dismissed_player_id": dismissed if is_wicket else None,
        "phase": phase,
        "pressure_index": p_index,
        "difficulty": diff,
        "wp_before": round(max(0.02, min(0.98, wp_before)), 3),
        "wp_after": round(max(0.02, min(0.98, wp_after)), 3),
        "batter_impact_delta": round(b_delta, 3),
        "bowler_impact_delta": round(bwl_delta, 3),
        "commentary": commentary,
    }


def _build_kkr_chase(target: int = 205):
    """
    Build ball-by-ball events for the KKR chase.
    Overs 1-19 use a seeded pseudo-realistic profile.
    Over 20 is hand-encoded exactly: 6,6,6,6,6 off Yash Dayal.
    """
    rng = random.Random(42)
    balls = []
    score = 0
    wickets = 0
    on_strike_idx = 0
    non_strike_idx = 1
    dismissed = set()

    # Realistic-ish over-by-over template runs (targeting ~175/6 after 19 to set up Rinku)
    # We aim to have exactly 176/6 after 19 so that KKR need 29 in the 20th.
    over_targets = [8, 6, 9, 12, 6, 10,  # PP (51/1)
                    7, 8, 9, 7, 10, 8, 9,  # middle
                    9, 7, 10, 11, 9, 12]   # 19 overs done — we'll adjust
    # Wickets: 1 in PP, 3 in middle, 2 in death (over 19 last one for Russell)
    wicket_overs = {2: "narine", 8: "gurbaz", 12: "venkatesh", 15: "nitish", 18: "russell"}

    for over_idx in range(19):  # overs 0..18 -> displayed as 1..19
        # Pick bowler
        bowler_pool = ["mohit", "rashid", "noor", "hardik", "alzarri", "yash"]
        bowler = bowler_pool[over_idx % len(bowler_pool)]
        phase = _phase(over_idx)

        target_over = over_targets[over_idx]
        remaining = target_over
        wicket_ball_idx = rng.randint(2, 5) if over_idx in wicket_overs else -1

        for ball_num in range(1, 7):
            batter = BATTING_ORDER[on_strike_idx]
            is_wicket = (ball_num == wicket_ball_idx and over_idx in wicket_overs and batter == wicket_overs[over_idx])

            if is_wicket:
                runs_b = 0
                extras = 0
                dismissed_id = batter
                wickets += 1
                dismissed.add(batter)
                # Bring in next batter
                new_idx = max(on_strike_idx, non_strike_idx) + 1
                on_strike_idx = new_idx
            else:
                # Distribute remaining runs across balls left
                balls_left = 6 - ball_num + 1
                # Weighted: bigger chance of dot/1 early, boundaries later
                avg = remaining / balls_left
                if avg > 3:
                    runs_b = rng.choices([1, 2, 4, 6], weights=[2, 2, 4, 3])[0]
                elif avg > 1.5:
                    runs_b = rng.choices([0, 1, 2, 4], weights=[2, 4, 3, 2])[0]
                else:
                    runs_b = rng.choices([0, 1], weights=[3, 4])[0]
                runs_b = min(runs_b, max(0, remaining))
                extras = 0
                dismissed_id = None
            remaining -= runs_b
            score += runs_b + extras

            wp_before = 1.0 - (max(0.0, (target - score - (runs_b + extras))) / max(1.0, target)) * 0.9
            wp_after = 1.0 - (max(0.0, (target - score)) / max(1.0, target)) * 0.9
            if is_wicket:
                wp_after -= 0.05

            balls.append(_make_ball(
                MATCH_ID, 2, over_idx, ball_num, batter, bowler,
                runs_b, is_wicket, dismissed_id, extras, phase,
                wp_before, wp_after, target=target, score=score, wickets=wickets,
            ))

            if runs_b in (1, 3) and not is_wicket:
                on_strike_idx, non_strike_idx = non_strike_idx, on_strike_idx

        # End of over: swap strike
        on_strike_idx, non_strike_idx = non_strike_idx, on_strike_idx

    # Force score after 19 overs to 176: adjust the delta by editing the last ball if needed
    while score < 176 and balls:
        balls[-1]["runs_batter"] += 1
        balls[-1]["runs_total"] += 1
        score += 1
    while score > 176 and balls:
        if balls[-1]["runs_batter"] > 0:
            balls[-1]["runs_batter"] -= 1
            balls[-1]["runs_total"] -= 1
            score -= 1
        else:
            break

    # ---- Over 20 (index 19): Rinku's 5 sixes off Yash Dayal ----
    # Make sure Rinku is on strike; if not, swap.
    # We assume Rinku is at index 5 (after wickets 1,2,3,4,5 = narine,gurbaz,venkatesh,nitish,russell).
    # After over 19 ended with Russell's wicket (over_idx=18), Rinku is on strike.
    over_20_runs = [6, 6, 6, 6, 6]  # 5 sixes on 5 legal balls (match won on ball 5)
    for i, r in enumerate(over_20_runs, start=1):
        wp_before = 1.0 - (max(0.0, (target - score)) / max(1.0, target)) * 0.9
        score += r
        wp_after = 1.0 - (max(0.0, (target - score)) / max(1.0, target)) * 0.9
        balls.append(_make_ball(
            MATCH_ID, 2, 19, i, "rinku", "yash", r, False, None, 0, "death",
            wp_before, wp_after, target=target, score=score, wickets=wickets,
        ))
        # Boost impact for these historic balls
        balls[-1]["batter_impact_delta"] = round(1.6 + (i * 0.15), 3)
        balls[-1]["bowler_impact_delta"] = round(-1.4 - (i * 0.12), 3)
        balls[-1]["commentary"] = f"SIX! Rinku Singh — {['first','second','third','fourth','fifth'][i-1]} six of the over!"

    return balls, score


# ---------- Ratings + Moments derivation ----------

def _compute_ratings_snapshots(balls: list[dict]) -> list[dict]:
    """Rolling per-player rating snapshots after each ball they were involved in."""
    snapshots = []
    running: dict[str, dict] = {}  # player_id -> {rating, components}

    for seq, b in enumerate(balls):
        for role, pid in [("batter", b["batter_id"]), ("bowler", b["bowler_id"])]:
            if not pid:
                continue
            st = running.setdefault(pid, {"rating": 6.0, "base": 6.0, "components": []})
            prev = st["rating"]

            # Compose the component for this ball
            if role == "batter":
                delta = b["batter_impact_delta"]
                if b["is_wicket"] and b["dismissed_player_id"] == pid:
                    label = f"Dismissed ({b['dismissal_type']}) at O{b['over']+1}.{b['ball']}"
                    reason = "WICKET_KEY_MOMENT"
                    delta = -0.9 - (b["pressure_index"] / 10) * 0.4
                elif b["runs_batter"] == 6:
                    label = f"Six under P={b['pressure_index']} (O{b['over']+1}.{b['ball']})"
                    reason = "PRESSURE_BOUNDARY"
                elif b["runs_batter"] == 4:
                    label = f"Four (O{b['over']+1}.{b['ball']})"
                    reason = "BOUNDARY"
                elif b["runs_batter"] == 0:
                    label = f"Dot ball (O{b['over']+1}.{b['ball']})"
                    reason = "DOT_UNDER_PRESSURE"
                else:
                    label = f"{b['runs_batter']} run{'s' if b['runs_batter']!=1 else ''} (O{b['over']+1}.{b['ball']})"
                    reason = "ROTATE_STRIKE"
            else:  # bowler
                delta = b["bowler_impact_delta"]
                if b["is_wicket"]:
                    label = f"Wicket, difficulty {b['difficulty']} (O{b['over']+1}.{b['ball']})"
                    reason = "WICKET_KEY_MOMENT"
                elif b["runs_total"] == 0:
                    label = f"Dot ball (O{b['over']+1}.{b['ball']})"
                    reason = "DOT_UNDER_PRESSURE"
                elif b["runs_total"] >= 4:
                    label = f"Conceded {b['runs_total']} (O{b['over']+1}.{b['ball']})"
                    reason = "CONCEDED_BOUNDARY"
                else:
                    label = f"Conceded {b['runs_total']} (O{b['over']+1}.{b['ball']})"
                    reason = "CONCEDED_MINOR"

            st["components"].append({
                "label": label, "weight": round(delta, 3), "ball_id": b["ball_id"],
                "reason_code": reason, "phase": b["phase"],
            })
            # Dampen delta for the rolling rating so ratings differentiate rather than saturate.
            # Component "weight" above is still the raw contribution — this only affects the
            # displayed rating trajectory. Real engine will replace this entirely.
            scaled = delta * 0.35
            new_rating = round(max(1.0, min(9.9, prev + scaled)), 2)
            st["rating"] = new_rating

            snapshots.append({
                "match_id": b["match_id"],
                "player_id": pid,
                "after_ball_id": b["ball_id"],
                "sequence": seq,
                "base_rating": st["base"],
                "components": list(st["components"]),  # cumulative
                "final_rating": new_rating,
                "delta": round(new_rating - prev, 3),
                "narrative": "",
            })
    return snapshots


def _flag_moments(balls: list[dict]) -> list[dict]:
    moments = []
    # Track biggest WP swings and wicket / boundary streaks
    for i, b in enumerate(balls):
        swing = abs(b["wp_after"] - b["wp_before"])
        if b["is_wicket"]:
            moments.append({
                "ball_id": b["ball_id"], "match_id": b["match_id"],
                "type": "wicket_key",
                "impact_score": round(swing * 30 + b["pressure_index"] / 2 + 2.0, 2),
                "narrative": f"Wicket in O{b['over']+1}.{b['ball']} — pressure index {b['pressure_index']}.",
                "over": b["over"], "ball": b["ball"], "sequence": i,
                "batter_id": b["batter_id"], "bowler_id": b["bowler_id"],
            })
        elif b["runs_batter"] == 6:
            is_finish_over = (b["over"] == 19)
            moments.append({
                "ball_id": b["ball_id"], "match_id": b["match_id"],
                "type": "match_turning_point" if is_finish_over else "boundary_streak",
                "impact_score": round(swing * 30 + b["pressure_index"] / 2 + (3.0 if is_finish_over else 0.5), 2),
                "narrative": (
                    f"Six under P={b['pressure_index']} shifts WP by {round(swing*100,1)}%."
                    if not is_finish_over
                    else f"Rinku six in O20 — pressure index {b['pressure_index']}, WP shift {round(swing*100,1)}%."
                ),
                "over": b["over"], "ball": b["ball"], "sequence": i,
                "batter_id": b["batter_id"], "bowler_id": b["bowler_id"],
            })
    # Sort by impact desc, keep top 12
    moments.sort(key=lambda m: m["impact_score"], reverse=True)
    return moments[:12]


# ---------- Seed entrypoint ----------

async def seed():
    db = get_db()

    # Clear prior seed for this match id (idempotent)
    await db.matches.delete_many({"match_id": MATCH_ID})
    await db.balls.delete_many({"match_id": MATCH_ID})
    await db.ratings_snapshots.delete_many({"match_id": MATCH_ID})
    await db.moments.delete_many({"match_id": MATCH_ID})
    # Players are shared; upsert
    for p in PLAYERS:
        await db.players.update_one({"player_id": p["player_id"]}, {"$set": p}, upsert=True)

    balls, final_score = _build_kkr_chase(target=205)

    # Match doc
    match_doc = {
        "match_id": MATCH_ID,
        "season": "IPL 2023",
        "date": "2023-04-09",
        "teams": ["Kolkata Knight Riders", "Gujarat Titans"],
        "team_short": ["KKR", "GT"],
        "venue": "Eden Gardens, Kolkata",
        "format": "T20",
        "status": "time_machine",
        "featured": True,
        "curation_slug": "rinku-5-sixes",
        "curation_title": "Rinku's 5 Sixes",
        "curation_hook": "KKR needed 29 off the last over. Watch every rating shift, ball by ball.",
        "result_summary": "KKR won by 3 wickets",
        "final_score": f"KKR {final_score}/6 (20) — GT 204/4 (20)",
        "ball_count": len(balls),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.matches.insert_one(match_doc)
    await db.balls.insert_many(balls)

    snaps = _compute_ratings_snapshots(balls)
    if snaps:
        await db.ratings_snapshots.insert_many(snaps)

    moments = _flag_moments(balls)
    if moments:
        await db.moments.insert_many(moments)

    # Indexes
    await db.balls.create_index([("match_id", 1), ("innings", 1), ("over", 1), ("ball", 1)])
    await db.ratings_snapshots.create_index([("match_id", 1), ("player_id", 1), ("sequence", 1)])
    await db.moments.create_index([("match_id", 1), ("impact_score", -1)])

    return {
        "match_id": MATCH_ID,
        "balls": len(balls),
        "ratings_snapshots": len(snaps),
        "moments": len(moments),
        "final_score": final_score,
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    print(asyncio.run(seed()))
